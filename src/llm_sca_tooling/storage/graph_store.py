"""Graph fact persistence and query primitives."""

from __future__ import annotations

import json
from sqlite3 import Connection, IntegrityError

from llm_sca_tooling.schemas.base import canonical_json
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType, SnapshotConsistency
from llm_sca_tooling.schemas.graph import GraphDiagnostic, GraphEdge, GraphNode
from llm_sca_tooling.storage.errors import GraphIntegrityError
from llm_sca_tooling.storage.graph_queries import GraphSlice, GraphStoreStatus
from llm_sca_tooling.storage.ids import payload_hash, snapshot_id_for
from llm_sca_tooling.storage.snapshots import SnapshotStore
from llm_sca_tooling.storage.transactions import transaction
from llm_sca_tooling.storage.workspace import _now_ts


class StoreWriteResult:
    def __init__(self, inserted: int, updated: int = 0) -> None:
        self.inserted = inserted
        self.updated = updated


class GraphStore:
    def __init__(self, conn: Connection, snapshots: SnapshotStore) -> None:
        self.conn = conn
        self.snapshots = snapshots

    def add_node(self, node: GraphNode) -> GraphNode:
        node = GraphNode.model_validate(node.model_dump(mode="python"))
        snapshot_id = self._ensure_snapshot(node)
        payload = node.model_dump(mode="json")
        phash = payload_hash(payload)
        existing = self.conn.execute("SELECT payload_hash FROM graph_nodes WHERE node_id=?", (node.node_id,)).fetchone()
        if existing:
            if existing["payload_hash"] != phash:
                raise GraphIntegrityError(f"duplicate node_id with different payload: {node.node_id}")
            return self.fetch_node(node.node_id)  # type: ignore[return-value]
        span = node.span
        self.conn.execute(
            """
            INSERT INTO graph_nodes(
              node_id, repo_id, snapshot_id, node_type, label, qualified_name, file_path,
              start_line, end_line, confidence, derivation, evidence_strength, provenance_hash,
              payload_hash, payload_json, created_ts, updated_ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node.node_id,
                node.repo.repo_id,
                snapshot_id,
                node.node_type.value,
                node.label,
                node.qualified_name,
                node.file_path,
                span.start_line if span else None,
                span.end_line if span else None,
                node.provenance.confidence,
                node.provenance.derivation.value,
                node.provenance.evidence_strength.value,
                payload_hash(node.provenance.model_dump(mode="json")),
                phash,
                canonical_json(payload),
                node.created_ts,
                _now_ts(),
            ),
        )
        self.conn.commit()
        return node

    def add_nodes(self, nodes: list[GraphNode]) -> StoreWriteResult:
        with transaction(self.conn, "add graph nodes"):
            for node in nodes:
                self._add_node_no_commit(node, upsert=False)
        return StoreWriteResult(inserted=len(nodes))

    def upsert_node(self, node: GraphNode) -> GraphNode:
        node = GraphNode.model_validate(node.model_dump(mode="python"))
        self._add_node_no_commit(node, upsert=True)
        self.conn.commit()
        return node

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        edge = GraphEdge.model_validate(edge.model_dump(mode="python"))
        self._add_edge_no_commit(edge, upsert=False)
        self.conn.commit()
        return edge

    def add_edges(self, edges: list[GraphEdge]) -> StoreWriteResult:
        with transaction(self.conn, "add graph edges"):
            for edge in edges:
                self._add_edge_no_commit(edge, upsert=False)
        return StoreWriteResult(inserted=len(edges))

    def upsert_edge(self, edge: GraphEdge) -> GraphEdge:
        edge = GraphEdge.model_validate(edge.model_dump(mode="python"))
        self._add_edge_no_commit(edge, upsert=True)
        self.conn.commit()
        return edge

    def fetch_node(self, node_id: str) -> GraphNode | None:
        row = self.conn.execute("SELECT payload_json FROM graph_nodes WHERE node_id=?", (node_id,)).fetchone()
        return None if row is None else GraphNode.model_validate_json(row["payload_json"])

    def fetch_edge(self, edge_id: str) -> GraphEdge | None:
        row = self.conn.execute("SELECT payload_json FROM graph_edges WHERE edge_id=?", (edge_id,)).fetchone()
        return None if row is None else GraphEdge.model_validate_json(row["payload_json"])

    def fetch_by_id(self, item_id: str) -> GraphNode | GraphEdge | None:
        return self.fetch_node(item_id) or self.fetch_edge(item_id)

    def fetch_nodes_by_type(self, repo_id: str, node_type: GraphNodeType, *, snapshot_id: str | None = None) -> list[GraphNode]:
        where = "repo_id=? AND node_type=?"
        params: list[object] = [repo_id, node_type.value]
        if snapshot_id:
            where += " AND snapshot_id=?"
            params.append(snapshot_id)
        return [GraphNode.model_validate_json(row["payload_json"]) for row in self.conn.execute(f"SELECT payload_json FROM graph_nodes WHERE {where}", params)]

    def fetch_edges_by_type(self, repo_id: str, edge_type: GraphEdgeType, *, snapshot_id: str | None = None) -> list[GraphEdge]:
        where = "repo_id=? AND edge_type=?"
        params: list[object] = [repo_id, edge_type.value]
        if snapshot_id:
            where += " AND snapshot_id=?"
            params.append(snapshot_id)
        return [GraphEdge.model_validate_json(row["payload_json"]) for row in self.conn.execute(f"SELECT payload_json FROM graph_edges WHERE {where}", params)]

    def fetch_neighbours(self, node_id: str, *, direction: str = "both", edge_types: list[GraphEdgeType] | None = None, depth: int = 1) -> GraphSlice:
        return self.fetch_ego_graph([node_id], depth=depth, edge_types=edge_types)

    def fetch_ego_graph(
        self,
        node_ids: list[str],
        *,
        depth: int = 1,
        edge_types: list[GraphEdgeType] | None = None,
        node_types: list[GraphNodeType] | None = None,
        limit: int | None = 2000,
    ) -> GraphSlice:
        seen_nodes = set(node_ids)
        frontier = set(node_ids)
        edge_ids: set[str] = set()
        edge_type_values = {edge_type.value for edge_type in edge_types or []}
        for _ in range(depth):
            if not frontier:
                break
            placeholders = ",".join("?" for _ in frontier)
            params: list[object] = list(frontier)
            filter_sql = ""
            if edge_type_values:
                filter_sql = f" AND edge_type IN ({','.join('?' for _ in edge_type_values)})"
                params.extend(edge_type_values)
            rows = self.conn.execute(
                f"SELECT edge_id, source_id, target_id FROM graph_edges WHERE (source_id IN ({placeholders}) OR target_id IN ({placeholders})) {filter_sql}",
                list(frontier) + params,
            ).fetchall()
            next_frontier: set[str] = set()
            for row in rows:
                edge_ids.add(row["edge_id"])
                for endpoint in (row["source_id"], row["target_id"]):
                    if endpoint not in seen_nodes:
                        seen_nodes.add(endpoint)
                        next_frontier.add(endpoint)
            frontier = next_frontier
            if limit is not None and len(seen_nodes) >= limit:
                break
        nodes = [self.fetch_node(node_id) for node_id in seen_nodes]
        nodes = [node for node in nodes if node is not None]
        if node_types:
            allowed = set(node_types)
            nodes = [node for node in nodes if node.node_type in allowed]
        edges = [self.fetch_edge(edge_id) for edge_id in edge_ids]
        edges = [edge for edge in edges if edge is not None]
        repo_id = nodes[0].repo.repo_id if nodes else ""
        return self._slice(repo_id, nodes, edges, requested_snapshot_id=None, limit=limit)

    def fetch_by_file(self, repo_id: str, file_path: str, *, snapshot_id: str | None = None) -> GraphSlice:
        params: list[object] = [repo_id, file_path]
        where = "repo_id=? AND file_path=?"
        if snapshot_id:
            where += " AND snapshot_id=?"
            params.append(snapshot_id)
        rows = self.conn.execute(f"SELECT payload_json FROM graph_nodes WHERE {where}", params).fetchall()
        nodes = [GraphNode.model_validate_json(row["payload_json"]) for row in rows]
        node_ids = [node.node_id for node in nodes]
        edges = self._edges_for_node_ids(node_ids)
        return self._slice(repo_id, nodes, edges, requested_snapshot_id=snapshot_id, limit=None)

    def fetch_by_span(self, repo_id: str, file_path: str, start_line: int, end_line: int, *, snapshot_id: str | None = None) -> GraphSlice:
        params: list[object] = [repo_id, file_path, end_line, start_line]
        where = "repo_id=? AND file_path=? AND start_line <= ? AND end_line >= ?"
        if snapshot_id:
            where += " AND snapshot_id=?"
            params.append(snapshot_id)
        rows = self.conn.execute(f"SELECT payload_json FROM graph_nodes WHERE {where}", params).fetchall()
        nodes = [GraphNode.model_validate_json(row["payload_json"]) for row in rows]
        return self._slice(repo_id, nodes, self._edges_for_node_ids([node.node_id for node in nodes]), requested_snapshot_id=snapshot_id, limit=None)

    def find_symbols(self, repo_id: str, qualified_name: str | None = None, file_path: str | None = None, snapshot_id: str | None = None) -> list[GraphNode]:
        clauses = ["repo_id=?", "node_type IN ('class','function','method','variable','type','interface')"]
        params: list[object] = [repo_id]
        if qualified_name:
            clauses.append("qualified_name=?")
            params.append(qualified_name)
        if file_path:
            clauses.append("file_path=?")
            params.append(file_path)
        if snapshot_id:
            clauses.append("snapshot_id=?")
            params.append(snapshot_id)
        return [GraphNode.model_validate_json(row["payload_json"]) for row in self.conn.execute(f"SELECT payload_json FROM graph_nodes WHERE {' AND '.join(clauses)}", params)]

    def find_edges_between(self, source_id: str, target_id: str, edge_type: GraphEdgeType | None = None) -> list[GraphEdge]:
        params: list[object] = [source_id, target_id]
        where = "source_id=? AND target_id=?"
        if edge_type:
            where += " AND edge_type=?"
            params.append(edge_type.value)
        return [GraphEdge.model_validate_json(row["payload_json"]) for row in self.conn.execute(f"SELECT payload_json FROM graph_edges WHERE {where}", params)]

    def count_nodes(self, repo_id: str, snapshot_id: str | None = None) -> int:
        return self._count("graph_nodes", repo_id, snapshot_id)

    def count_edges(self, repo_id: str, snapshot_id: str | None = None) -> int:
        return self._count("graph_edges", repo_id, snapshot_id)

    def graph_status(self, repo_id: str, snapshot_id: str | None = None) -> GraphStoreStatus:
        slice_result = self.fetch_by_file(repo_id, "", snapshot_id=snapshot_id) if False else None
        snapshot_ids = self._snapshot_ids_for_repo(repo_id, snapshot_id)
        mix = self.snapshots.detect_mixed_snapshots(snapshot_ids) if snapshot_ids else None
        return GraphStoreStatus(
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            node_count=self.count_nodes(repo_id, snapshot_id),
            edge_count=self.count_edges(repo_id, snapshot_id),
            snapshot_consistency=mix.snapshot_consistency if mix else SnapshotConsistency.UNKNOWN,
        )

    def _add_node_no_commit(self, node: GraphNode, *, upsert: bool) -> None:
        node = GraphNode.model_validate(node.model_dump(mode="python"))
        snapshot_id = self._ensure_snapshot(node)
        payload = node.model_dump(mode="json")
        phash = payload_hash(payload)
        existing = self.conn.execute("SELECT payload_hash FROM graph_nodes WHERE node_id=?", (node.node_id,)).fetchone()
        if existing and not upsert:
            if existing["payload_hash"] != phash:
                raise GraphIntegrityError(f"duplicate node_id with different payload: {node.node_id}")
            return
        span = node.span
        self.conn.execute(
            """
            INSERT INTO graph_nodes(node_id, repo_id, snapshot_id, node_type, label, qualified_name, file_path,
              start_line, end_line, confidence, derivation, evidence_strength, provenance_hash,
              payload_hash, payload_json, created_ts, updated_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
              snapshot_id=excluded.snapshot_id,
              node_type=excluded.node_type,
              label=excluded.label,
              qualified_name=excluded.qualified_name,
              file_path=excluded.file_path,
              start_line=excluded.start_line,
              end_line=excluded.end_line,
              confidence=excluded.confidence,
              derivation=excluded.derivation,
              evidence_strength=excluded.evidence_strength,
              provenance_hash=excluded.provenance_hash,
              payload_hash=excluded.payload_hash,
              payload_json=excluded.payload_json,
              updated_ts=excluded.updated_ts
            """,
            (
                node.node_id,
                node.repo.repo_id,
                snapshot_id,
                node.node_type.value,
                node.label,
                node.qualified_name,
                node.file_path,
                span.start_line if span else None,
                span.end_line if span else None,
                node.provenance.confidence,
                node.provenance.derivation.value,
                node.provenance.evidence_strength.value,
                payload_hash(node.provenance.model_dump(mode="json")),
                phash,
                canonical_json(payload),
                node.created_ts,
                _now_ts(),
            ),
        )

    def _add_edge_no_commit(self, edge: GraphEdge, *, upsert: bool) -> None:
        edge = GraphEdge.model_validate(edge.model_dump(mode="python"))
        if not self.fetch_node(edge.source_id) or not self.fetch_node(edge.target_id):
            raise GraphIntegrityError(f"edge {edge.edge_id} references missing endpoints")
        snapshot_id = self._ensure_snapshot(edge)
        payload = edge.model_dump(mode="json")
        phash = payload_hash(payload)
        existing = self.conn.execute("SELECT payload_hash FROM graph_edges WHERE edge_id=?", (edge.edge_id,)).fetchone()
        if existing and not upsert:
            if existing["payload_hash"] != phash:
                raise GraphIntegrityError(f"duplicate edge_id with different payload: {edge.edge_id}")
            return
        try:
            self.conn.execute(
                """
                INSERT INTO graph_edges(edge_id, repo_id, snapshot_id, edge_type, source_id, target_id,
                  confidence, derivation, evidence_strength, provenance_hash, payload_hash, payload_json, created_ts, updated_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(edge_id) DO UPDATE SET
                  snapshot_id=excluded.snapshot_id,
                  edge_type=excluded.edge_type,
                  source_id=excluded.source_id,
                  target_id=excluded.target_id,
                  confidence=excluded.confidence,
                  derivation=excluded.derivation,
                  evidence_strength=excluded.evidence_strength,
                  provenance_hash=excluded.provenance_hash,
                  payload_hash=excluded.payload_hash,
                  payload_json=excluded.payload_json,
                  updated_ts=excluded.updated_ts
                """,
                (
                    edge.edge_id,
                    edge.repo.repo_id,
                    snapshot_id,
                    edge.edge_type.value,
                    edge.source_id,
                    edge.target_id,
                    edge.confidence,
                    edge.provenance.derivation.value,
                    edge.provenance.evidence_strength.value,
                    payload_hash(edge.provenance.model_dump(mode="json")),
                    phash,
                    canonical_json(payload),
                    edge.created_ts,
                    _now_ts(),
                ),
            )
        except IntegrityError as exc:
            raise GraphIntegrityError(str(exc)) from exc

    def _ensure_snapshot(self, item: GraphNode | GraphEdge) -> str:
        record = self.snapshots.record_snapshot(item.snapshot)
        return record.snapshot_id

    def _edges_for_node_ids(self, node_ids: list[str]) -> list[GraphEdge]:
        if not node_ids:
            return []
        placeholders = ",".join("?" for _ in node_ids)
        rows = self.conn.execute(
            f"SELECT payload_json FROM graph_edges WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})",
            node_ids + node_ids,
        ).fetchall()
        return [GraphEdge.model_validate_json(row["payload_json"]) for row in rows]

    def _slice(self, repo_id: str, nodes: list[GraphNode], edges: list[GraphEdge], *, requested_snapshot_id: str | None, limit: int | None) -> GraphSlice:
        truncated = False
        if limit is not None and len(nodes) > limit:
            nodes = nodes[:limit]
            truncated = True
        snapshot_ids = sorted(
            {
                snapshot_id_for(node.snapshot)
                for node in nodes
            }
            | {snapshot_id_for(edge.snapshot) for edge in edges}
        )
        mix = self.snapshots.detect_mixed_snapshots(snapshot_ids) if snapshot_ids else None
        return GraphSlice(
            repo_id=repo_id,
            requested_snapshot_id=requested_snapshot_id,
            snapshot_ids=snapshot_ids,
            snapshot_consistency=mix.snapshot_consistency if mix else SnapshotConsistency.UNKNOWN,
            nodes=nodes,
            edges=edges,
            truncated=truncated,
            limit=limit,
            provenance_summary={"node_count": len(nodes), "edge_count": len(edges)},
        )

    def _snapshot_ids_for_repo(self, repo_id: str, snapshot_id: str | None) -> list[str]:
        if snapshot_id:
            return [snapshot_id]
        rows = self.conn.execute("SELECT DISTINCT snapshot_id FROM graph_nodes WHERE repo_id=?", (repo_id,)).fetchall()
        return [row["snapshot_id"] for row in rows]

    def _count(self, table: str, repo_id: str, snapshot_id: str | None) -> int:
        if snapshot_id:
            row = self.conn.execute(f"SELECT count(*) AS count FROM {table} WHERE repo_id=? AND snapshot_id=?", (repo_id, snapshot_id)).fetchone()
        else:
            row = self.conn.execute(f"SELECT count(*) AS count FROM {table} WHERE repo_id=?", (repo_id,)).fetchone()
        return int(row["count"])
