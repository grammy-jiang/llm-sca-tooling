"""Graph slice generator for files and symbols."""

from __future__ import annotations

from llm_sca_tooling.storage.graph_queries import GraphSlice
from llm_sca_tooling.storage.workspace import WorkspaceStore


class GraphSliceGenerator:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def by_file(
        self, repo_id: str, file_path: str, *, depth: int = 1, limit: int = 2000
    ) -> GraphSlice:
        base = self.workspace.graph.fetch_by_file(repo_id, file_path)
        node_ids = [node.node_id for node in base.nodes]
        if not node_ids:
            return base
        return self.workspace.graph.fetch_ego_graph(node_ids, depth=depth, limit=limit)

    def by_symbol(
        self, repo_id: str, symbol: str, *, depth: int = 1, limit: int = 2000
    ) -> GraphSlice:
        nodes = []
        if symbol.startswith("node:"):
            node = self.workspace.graph.fetch_node(symbol)
            nodes = [node] if node else []
        else:
            nodes = self.workspace.graph.find_symbols(repo_id, qualified_name=symbol)
        if not nodes:
            return GraphSlice(
                repo_id=repo_id,
                requested_snapshot_id=None,
                snapshot_ids=[],
                snapshot_consistency="unknown",
                nodes=[],
                edges=[],
                truncated=False,
                limit=limit,
            )
        return self.workspace.graph.fetch_ego_graph(
            [node.node_id for node in nodes], depth=depth, limit=limit
        )
