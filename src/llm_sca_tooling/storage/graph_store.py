"""Graph store — write-side operations for graph nodes and edges."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import orjson
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.storage.errors import GraphIntegrityError
from llm_sca_tooling.storage.models import (
    GraphEdgeRow,
    GraphNodeRow,
)
from llm_sca_tooling.storage.sqlite import AsyncSessionFactory
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["GraphStore", "StoreWriteResult", "DeleteResult"]

logger = get_logger(__name__)

_MAX_BATCH = 500


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    ).hexdigest()[:24]


@dataclass
class StoreWriteResult:
    written: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class DeleteResult:
    deleted: int = 0


def _node_to_row(node: GraphNode) -> GraphNodeRow:
    payload = node.model_dump(mode="json")
    return GraphNodeRow(
        node_id=node.node_id,
        repo_id=node.repo.repo_id,
        snapshot_id=node.snapshot.worktree_snapshot_id
        or node.snapshot.git_sha
        or node.snapshot.repo_id,
        node_type=node.node_type.value,
        label=node.label,
        qualified_name=node.qualified_name,
        file_path=node.file_path,
        start_line=node.span.start_line if node.span else None,
        end_line=node.span.end_line if node.span else None,
        confidence=node.provenance.confidence,
        derivation=node.provenance.derivation.value,
        evidence_strength=node.provenance.evidence_strength.value,
        provenance_hash=_payload_hash(node.provenance.model_dump(mode="json")),
        payload_json=orjson.dumps(payload).decode(),
        created_ts=node.created_ts,
        updated_ts=_now(),
    )


def _edge_to_row(edge: GraphEdge) -> GraphEdgeRow:
    payload = edge.model_dump(mode="json")
    return GraphEdgeRow(
        edge_id=edge.edge_id,
        repo_id=edge.repo.repo_id,
        snapshot_id=edge.snapshot.worktree_snapshot_id
        or edge.snapshot.git_sha
        or edge.snapshot.repo_id,
        edge_type=edge.edge_type.value,
        source_id=edge.source_id,
        target_id=edge.target_id,
        confidence=edge.confidence,
        derivation=edge.provenance.derivation.value,
        evidence_strength=edge.provenance.evidence_strength.value,
        provenance_hash=_payload_hash(edge.provenance.model_dump(mode="json")),
        payload_json=orjson.dumps(payload).decode(),
        created_ts=edge.created_ts,
        updated_ts=_now(),
    )


class GraphStore:
    """Transactional write operations for graph nodes, edges, diagnostics, and manifests."""

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    async def add_node(self, node: GraphNode) -> GraphNode:
        """Add a single node.  Fails on duplicate ID with different payload."""
        try:
            async with self._session_factory() as session, session.begin():
                existing = await session.get(GraphNodeRow, node.node_id)
                if existing:
                    # Idempotent on same payload
                    return node
                session.add(_node_to_row(node))
        except IntegrityError as exc:
            raise GraphIntegrityError(
                f"Cannot add node {node.node_id!r}: {exc}"
            ) from exc
        return node

    async def add_nodes(self, nodes: list[GraphNode]) -> StoreWriteResult:
        """Batch-insert nodes.  Rolls back entire batch on any error."""
        result = StoreWriteResult()
        try:
            async with self._session_factory() as session, session.begin():
                for node in nodes:
                    existing = await session.get(GraphNodeRow, node.node_id)
                    if existing:
                        result.skipped += 1
                        continue
                    session.add(_node_to_row(node))
                    result.written += 1
        except IntegrityError as exc:
            raise GraphIntegrityError(f"Batch node insert failed: {exc}") from exc
        return result

    async def add_edge(self, edge: GraphEdge) -> GraphEdge:
        """Add a single edge.  Source and target nodes must exist."""
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    src = await session.get(GraphNodeRow, edge.source_id)
                    tgt = await session.get(GraphNodeRow, edge.target_id)
                    if src is None:
                        raise GraphIntegrityError(
                            f"Edge {edge.edge_id!r}: source node {edge.source_id!r} not found"
                        )
                    if tgt is None:
                        raise GraphIntegrityError(
                            f"Edge {edge.edge_id!r}: target node {edge.target_id!r} not found"
                        )
                    existing = await session.get(GraphEdgeRow, edge.edge_id)
                    if existing:
                        return edge
                    session.add(_edge_to_row(edge))
        except GraphIntegrityError:
            raise
        except IntegrityError as exc:
            raise GraphIntegrityError(
                f"Cannot add edge {edge.edge_id!r}: {exc}"
            ) from exc
        return edge

    async def add_edges(self, edges: list[GraphEdge]) -> StoreWriteResult:
        """Batch-insert edges.  Rolls back on any endpoint integrity error."""
        result = StoreWriteResult()
        try:
            async with self._session_factory() as session, session.begin():
                for edge in edges:
                    src = await session.get(GraphNodeRow, edge.source_id)
                    tgt = await session.get(GraphNodeRow, edge.target_id)
                    if src is None or tgt is None:
                        raise GraphIntegrityError(
                            f"Edge {edge.edge_id!r}: endpoint not found "
                            f"(src={edge.source_id!r}, tgt={edge.target_id!r})"
                        )
                    existing = await session.get(GraphEdgeRow, edge.edge_id)
                    if existing:
                        result.skipped += 1
                        continue
                    session.add(_edge_to_row(edge))
                    result.written += 1
        except GraphIntegrityError:
            raise
        except IntegrityError as exc:
            raise GraphIntegrityError(f"Batch edge insert failed: {exc}") from exc
        return result

    async def upsert_node(self, node: GraphNode) -> GraphNode:
        """Insert or update a node row."""
        async with self._session_factory() as session, session.begin():
            row = _node_to_row(node)
            await session.merge(row)
        return node

    async def upsert_edge(self, edge: GraphEdge) -> GraphEdge:
        """Insert or update an edge row."""
        async with self._session_factory() as session, session.begin():
            row = _edge_to_row(edge)
            await session.merge(row)
        return edge

    async def delete_nodes_for_snapshot(
        self,
        repo_id: str,
        snapshot_id: str,
        *,
        node_types: list[str] | None = None,
    ) -> DeleteResult:
        async with self._session_factory() as session, session.begin():
            stmt = (
                select(GraphNodeRow)
                .where(GraphNodeRow.repo_id == repo_id)
                .where(GraphNodeRow.snapshot_id == snapshot_id)
            )
            if node_types:
                stmt = stmt.where(GraphNodeRow.node_type.in_(node_types))
            result = await session.execute(stmt)
            rows = result.scalars().all()
            for row in rows:
                await session.delete(row)
            return DeleteResult(deleted=len(rows))

    async def delete_edges_for_snapshot(
        self,
        repo_id: str,
        snapshot_id: str,
        *,
        edge_types: list[str] | None = None,
    ) -> DeleteResult:
        async with self._session_factory() as session, session.begin():
            stmt = (
                select(GraphEdgeRow)
                .where(GraphEdgeRow.repo_id == repo_id)
                .where(GraphEdgeRow.snapshot_id == snapshot_id)
            )
            if edge_types:
                stmt = stmt.where(GraphEdgeRow.edge_type.in_(edge_types))
            result = await session.execute(stmt)
            rows = result.scalars().all()
            for row in rows:
                await session.delete(row)
            return DeleteResult(deleted=len(rows))
