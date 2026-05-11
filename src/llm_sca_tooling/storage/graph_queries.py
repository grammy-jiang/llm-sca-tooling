"""Graph query layer — fetch and traverse stored graph facts.

Large traversals use NetworkX loaded on demand from SQLModel rows.
NetworkX is never stored persistently; it is a query-time projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx
import orjson
from sqlalchemy import select

from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.storage.models import GraphEdgeRow, GraphNodeRow
from llm_sca_tooling.storage.sqlite import AsyncSessionFactory
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["GraphQueryStore", "GraphSlice"]

logger = get_logger(__name__)

_DEFAULT_NODE_LIMIT = 2_000
_DEFAULT_EDGE_LIMIT = 5_000


def _row_to_node(row: GraphNodeRow) -> GraphNode:
    return GraphNode.model_validate(orjson.loads(row.payload_json))


def _row_to_edge(row: GraphEdgeRow) -> GraphEdge:
    return GraphEdge.model_validate(orjson.loads(row.payload_json))


@dataclass
class GraphSlice:
    """Result of a graph query, including snapshot consistency metadata."""

    repo_id: str
    requested_snapshot_id: str | None
    snapshot_ids: list[str]
    snapshot_consistency: str  # clean | mixed | unknown
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    diagnostics: list[dict[str, Any]]
    truncated: bool
    limit: int | None
    provenance_summary: str


def _consistency(snapshot_ids: list[str]) -> str:
    unique = set(snapshot_ids)
    if len(unique) <= 1:
        return "clean"
    return "mixed"


class GraphQueryStore:
    """Read-only graph queries built on top of SQLModel rows."""

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    async def fetch_node(self, node_id: str) -> GraphNode | None:
        async with self._session_factory() as session:
            row = await session.get(GraphNodeRow, node_id)
        return _row_to_node(row) if row else None

    async def fetch_edge(self, edge_id: str) -> GraphEdge | None:
        async with self._session_factory() as session:
            row = await session.get(GraphEdgeRow, edge_id)
        return _row_to_edge(row) if row else None

    async def fetch_nodes_by_type(
        self,
        repo_id: str,
        node_type: str,
        *,
        snapshot_id: str | None = None,
        limit: int | None = _DEFAULT_NODE_LIMIT,
    ) -> list[GraphNode]:
        async with self._session_factory() as session:
            stmt = (
                select(GraphNodeRow)
                .where(GraphNodeRow.repo_id == repo_id)
                .where(GraphNodeRow.node_type == node_type)
            )
            if snapshot_id:
                stmt = stmt.where(GraphNodeRow.snapshot_id == snapshot_id)
            if limit:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [_row_to_node(r) for r in rows]

    async def fetch_edges_by_type(
        self,
        repo_id: str,
        edge_type: str,
        *,
        snapshot_id: str | None = None,
        limit: int | None = _DEFAULT_EDGE_LIMIT,
    ) -> list[GraphEdge]:
        async with self._session_factory() as session:
            stmt = (
                select(GraphEdgeRow)
                .where(GraphEdgeRow.repo_id == repo_id)
                .where(GraphEdgeRow.edge_type == edge_type)
            )
            if snapshot_id:
                stmt = stmt.where(GraphEdgeRow.snapshot_id == snapshot_id)
            if limit:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [_row_to_edge(r) for r in rows]

    async def fetch_by_file(
        self,
        repo_id: str,
        file_path: str,
        *,
        snapshot_id: str | None = None,
        limit: int = _DEFAULT_NODE_LIMIT,
    ) -> GraphSlice:
        async with self._session_factory() as session:
            stmt = (
                select(GraphNodeRow)
                .where(GraphNodeRow.repo_id == repo_id)
                .where(GraphNodeRow.file_path == file_path)
                .limit(limit + 1)
            )
            if snapshot_id:
                stmt = stmt.where(GraphNodeRow.snapshot_id == snapshot_id)
            result = await session.execute(stmt)
            rows = result.scalars().all()

        truncated = len(rows) > limit
        rows = rows[:limit]
        nodes = [_row_to_node(r) for r in rows]
        snap_ids = list({r.snapshot_id for r in rows[:limit]})

        return GraphSlice(
            repo_id=repo_id,
            requested_snapshot_id=snapshot_id,
            snapshot_ids=snap_ids,
            snapshot_consistency=_consistency(snap_ids),
            nodes=nodes,
            edges=[],
            diagnostics=[],
            truncated=truncated,
            limit=limit,
            provenance_summary=f"{len(nodes)} nodes from {file_path}",
        )

    async def fetch_by_span(
        self,
        repo_id: str,
        file_path: str,
        start_line: int,
        end_line: int,
        *,
        snapshot_id: str | None = None,
    ) -> GraphSlice:
        async with self._session_factory() as session:
            stmt = (
                select(GraphNodeRow)
                .where(GraphNodeRow.repo_id == repo_id)
                .where(GraphNodeRow.file_path == file_path)
                .where(GraphNodeRow.start_line >= start_line)
                .where(GraphNodeRow.end_line <= end_line)
            )
            if snapshot_id:
                stmt = stmt.where(GraphNodeRow.snapshot_id == snapshot_id)
            result = await session.execute(stmt)
            rows = result.scalars().all()

        nodes = [_row_to_node(r) for r in rows]
        snap_ids = list({r.snapshot_id for r in rows})
        return GraphSlice(
            repo_id=repo_id,
            requested_snapshot_id=snapshot_id,
            snapshot_ids=snap_ids,
            snapshot_consistency=_consistency(snap_ids),
            nodes=nodes,
            edges=[],
            diagnostics=[],
            truncated=False,
            limit=None,
            provenance_summary=f"{len(nodes)} nodes in {file_path}:{start_line}-{end_line}",
        )

    async def fetch_neighbours(
        self,
        node_id: str,
        *,
        direction: str = "both",
        edge_types: list[str] | None = None,
        depth: int = 1,
        limit: int = _DEFAULT_NODE_LIMIT,
    ) -> GraphSlice:
        """Return immediate neighbours of *node_id*."""
        async with self._session_factory() as session:
            source_row = await session.get(GraphNodeRow, node_id)
            if source_row is None:
                return GraphSlice(
                    repo_id="",
                    requested_snapshot_id=None,
                    snapshot_ids=[],
                    snapshot_consistency="unknown",
                    nodes=[],
                    edges=[],
                    diagnostics=[],
                    truncated=False,
                    limit=limit,
                    provenance_summary=f"node {node_id!r} not found",
                )

            repo_id = source_row.repo_id
            edge_stmt = select(GraphEdgeRow).where(GraphEdgeRow.repo_id == repo_id)
            if direction in ("out", "both"):
                src_stmt = edge_stmt.where(GraphEdgeRow.source_id == node_id)
            else:
                src_stmt = edge_stmt.where(GraphEdgeRow.source_id == "")

            if direction in ("in", "both"):
                tgt_stmt = edge_stmt.where(GraphEdgeRow.target_id == node_id)
            else:
                tgt_stmt = edge_stmt.where(GraphEdgeRow.target_id == "")

            if edge_types:
                src_stmt = src_stmt.where(GraphEdgeRow.edge_type.in_(edge_types))
                tgt_stmt = tgt_stmt.where(GraphEdgeRow.edge_type.in_(edge_types))

            out_edges = (await session.execute(src_stmt)).scalars().all()
            in_edges = (await session.execute(tgt_stmt)).scalars().all()
            all_edge_rows = list(out_edges) + list(in_edges)

            neighbour_ids = {e.target_id for e in out_edges} | {
                e.source_id for e in in_edges
            }
            neighbour_ids.discard(node_id)

            node_rows = []
            for nid in list(neighbour_ids)[:limit]:
                nrow = await session.get(GraphNodeRow, nid)
                if nrow:
                    node_rows.append(nrow)

        edges = [_row_to_edge(e) for e in all_edge_rows]
        nodes = [_row_to_node(n) for n in node_rows]
        snap_ids = list({r.snapshot_id for r in node_rows})

        return GraphSlice(
            repo_id=repo_id,
            requested_snapshot_id=None,
            snapshot_ids=snap_ids,
            snapshot_consistency=_consistency(snap_ids),
            nodes=nodes,
            edges=edges,
            diagnostics=[],
            truncated=len(neighbour_ids) > limit,
            limit=limit,
            provenance_summary=f"{len(nodes)} neighbours of {node_id!r}",
        )

    async def fetch_ego_graph(
        self,
        node_ids: list[str],
        *,
        depth: int = 1,
        edge_types: list[str] | None = None,
        node_types: list[str] | None = None,
        limit: int = _DEFAULT_NODE_LIMIT,
    ) -> GraphSlice:
        """Return the ego graph around *node_ids* up to *depth* hops.

        Loads a bounded subgraph into NetworkX for traversal, then returns
        nodes and edges with snapshot consistency metadata.
        """
        if not node_ids:
            return GraphSlice(
                repo_id="",
                requested_snapshot_id=None,
                snapshot_ids=[],
                snapshot_consistency="unknown",
                nodes=[],
                edges=[],
                diagnostics=[],
                truncated=False,
                limit=limit,
                provenance_summary="empty input",
            )

        # Fetch seed nodes to determine repo_id
        async with self._session_factory() as session:
            seed_rows = []
            for nid in node_ids:
                row = await session.get(GraphNodeRow, nid)
                if row:
                    seed_rows.append(row)

        if not seed_rows:
            return GraphSlice(
                repo_id="",
                requested_snapshot_id=None,
                snapshot_ids=[],
                snapshot_consistency="unknown",
                nodes=[],
                edges=[],
                diagnostics=[{"message": f"none of {node_ids} found"}],
                truncated=False,
                limit=limit,
                provenance_summary="nodes not found",
            )

        repo_id = seed_rows[0].repo_id

        # Load a bounded subgraph into memory for NetworkX traversal
        async with self._session_factory() as session:
            edge_stmt = (
                select(GraphEdgeRow)
                .where(GraphEdgeRow.repo_id == repo_id)
                .limit(_DEFAULT_EDGE_LIMIT)
            )
            if edge_types:
                edge_stmt = edge_stmt.where(GraphEdgeRow.edge_type.in_(edge_types))
            edge_rows = (await session.execute(edge_stmt)).scalars().all()

            node_stmt = (
                select(GraphNodeRow)
                .where(GraphNodeRow.repo_id == repo_id)
                .limit(_DEFAULT_NODE_LIMIT)
            )
            if node_types:
                node_stmt = node_stmt.where(GraphNodeRow.node_type.in_(node_types))
            node_rows = (await session.execute(node_stmt)).scalars().all()

        # Build NetworkX graph
        g: nx.DiGraph = nx.DiGraph()
        node_map = {r.node_id: r for r in node_rows}
        for row in node_rows:
            g.add_node(row.node_id)
        for row in edge_rows:
            g.add_edge(row.source_id, row.target_id)

        # Compute ego graph union over all seed nodes
        ego_nodes: set[str] = set()
        for seed_id in node_ids:
            if seed_id in g:
                ego = nx.ego_graph(g, seed_id, radius=depth, undirected=True)
                ego_nodes.update(ego.nodes())

        truncated = len(ego_nodes) > limit
        ego_nodes_limited = set(list(ego_nodes)[:limit])

        result_nodes = [
            _row_to_node(node_map[nid]) for nid in ego_nodes_limited if nid in node_map
        ]
        result_edges = [
            _row_to_edge(r)
            for r in edge_rows
            if r.source_id in ego_nodes_limited and r.target_id in ego_nodes_limited
        ]
        snap_ids = list(
            {r.snapshot_id for r in node_rows if r.node_id in ego_nodes_limited}
        )

        return GraphSlice(
            repo_id=repo_id,
            requested_snapshot_id=None,
            snapshot_ids=snap_ids,
            snapshot_consistency=_consistency(snap_ids),
            nodes=result_nodes,
            edges=result_edges,
            diagnostics=[],
            truncated=truncated,
            limit=limit,
            provenance_summary=f"ego graph depth={depth}, {len(result_nodes)} nodes",
        )

    async def count_nodes(self, repo_id: str, snapshot_id: str | None = None) -> int:
        from sqlalchemy import func

        async with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(GraphNodeRow)
                .where(GraphNodeRow.repo_id == repo_id)
            )
            if snapshot_id:
                stmt = stmt.where(GraphNodeRow.snapshot_id == snapshot_id)
            result = await session.execute(stmt)
            return result.scalar_one() or 0

    async def count_edges(self, repo_id: str, snapshot_id: str | None = None) -> int:
        from sqlalchemy import func

        async with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(GraphEdgeRow)
                .where(GraphEdgeRow.repo_id == repo_id)
            )
            if snapshot_id:
                stmt = stmt.where(GraphEdgeRow.snapshot_id == snapshot_id)
            result = await session.execute(stmt)
            return result.scalar_one() or 0
