"""Graph slice generator — bounded context units for MCP and LLM workflows."""

from __future__ import annotations

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.storage.graph_queries import GraphQueryStore, GraphSlice

__all__ = ["GraphSliceGenerator"]


class GraphSliceGenerator:
    """Generate bounded graph slices using Phase 2 graph query primitives."""

    def __init__(self, query_store: GraphQueryStore, config: IndexingConfig) -> None:
        self._store = query_store
        self._config = config

    async def slice_by_file(
        self,
        repo_id: str,
        file_path: str,
        snapshot_id: str | None = None,
    ) -> GraphSlice:
        """Return a graph slice for a file plus immediate symbol neighbours."""
        base = await self._store.fetch_by_file(
            repo_id,
            file_path,
            snapshot_id=snapshot_id,
            limit=self._config.graph_slice_limit,
        )
        return await self._expand(base)

    async def slice_by_symbol(
        self,
        node_id: str,
        *,
        depth: int = 1,
        limit: int | None = None,
    ) -> GraphSlice:
        """Return an ego graph slice around a symbol node."""
        base = await self._store.fetch_ego_graph(
            [node_id],
            depth=depth,
            limit=limit or self._config.graph_slice_limit,
        )
        return await self._expand(base)

    async def slice_by_span(
        self,
        repo_id: str,
        file_path: str,
        start_line: int,
        end_line: int,
        snapshot_id: str | None = None,
    ) -> GraphSlice:
        """Return nodes whose spans intersect [start_line, end_line]."""
        base = await self._store.fetch_by_span(
            repo_id,
            file_path,
            start_line,
            end_line,
            snapshot_id=snapshot_id,
        )
        return await self._expand(base)

    async def _expand(self, base: GraphSlice) -> GraphSlice:
        """Expand a base slice with one-hop neighbours and merge metadata."""
        nodes_by_id: dict[str, GraphNode] = {node.node_id: node for node in base.nodes}
        edges_by_id: dict[str, GraphEdge] = {edge.edge_id: edge for edge in base.edges}
        diagnostics = list(base.diagnostics)
        snapshot_ids = set(base.snapshot_ids)
        truncated = base.truncated

        for node_id in list(nodes_by_id):
            neighbours = await self._store.fetch_neighbours(
                node_id,
                direction="both",
                edge_types=["contains", "imports", "tests", "calls"],
                limit=self._config.graph_slice_limit,
            )
            for node in neighbours.nodes:
                nodes_by_id.setdefault(node.node_id, node)
            for edge in neighbours.edges:
                edges_by_id.setdefault(edge.edge_id, edge)
            diagnostics.extend(neighbours.diagnostics)
            snapshot_ids.update(neighbours.snapshot_ids)
            truncated = truncated or neighbours.truncated

        consistency = "clean" if len(snapshot_ids) <= 1 else "mixed"
        if not snapshot_ids and base.snapshot_consistency == "unknown":
            consistency = "unknown"

        return GraphSlice(
            repo_id=base.repo_id,
            requested_snapshot_id=base.requested_snapshot_id,
            snapshot_ids=sorted(snapshot_ids),
            snapshot_consistency=consistency,
            nodes=list(nodes_by_id.values()),
            edges=list(edges_by_id.values()),
            diagnostics=diagnostics,
            truncated=truncated,
            limit=base.limit,
            provenance_summary=base.provenance_summary + "; expanded one hop",
        )
