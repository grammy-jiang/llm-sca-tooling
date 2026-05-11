"""Graph-path helpers for repo-QA answers."""

from __future__ import annotations

from collections import deque

from pydantic import Field

from llm_sca_tooling.qa.lookup import GraphNodeRef
from llm_sca_tooling.qa.question import StrictQaModel
from llm_sca_tooling.storage.graph_queries import GraphQueryStore

__all__ = ["DocumentLink", "GraphPath", "GraphPathBuilder"]


class GraphPath(StrictQaModel):
    path_id: str
    node_ids: list[str]
    edge_ids: list[str] = Field(default_factory=list)
    confidence: str = "heuristic"


class DocumentLink(StrictQaModel):
    node_id: str
    document_node_id: str
    confidence: str = "heuristic"


class GraphPathBuilder:
    def __init__(self, graph: GraphQueryStore) -> None:
        self._graph = graph

    async def build_path(
        self, start_node_id: str, target_node_id: str, *, max_hops: int = 8
    ) -> GraphPath | None:
        queue: deque[tuple[str, list[str], list[str]]] = deque(
            [(start_node_id, [start_node_id], [])]
        )
        visited = {start_node_id}
        while queue:
            node_id, path, edges = queue.popleft()
            if node_id == target_node_id:
                return GraphPath(
                    path_id="path:" + "->".join(path),
                    node_ids=path,
                    edge_ids=edges,
                    confidence="heuristic",
                )
            if len(path) > max_hops:
                continue
            graph_slice = await self._graph.fetch_neighbours(node_id)
            for edge in graph_slice.edges:
                next_id = (
                    edge.target_id if edge.source_id == node_id else edge.source_id
                )
                if next_id in visited:
                    continue
                visited.add(next_id)
                queue.append((next_id, [*path, next_id], [*edges, edge.edge_id]))
        return None

    async def linked_documents(self, node: GraphNodeRef) -> list[DocumentLink]:
        links: list[DocumentLink] = []
        graph_slice = await self._graph.fetch_neighbours(node.node_id)
        for edge in graph_slice.edges:
            if edge.edge_type.value == "documents":
                other = (
                    edge.target_id if edge.source_id == node.node_id else edge.source_id
                )
                links.append(
                    DocumentLink(
                        node_id=node.node_id,
                        document_node_id=other,
                        confidence="parser" if edge.confidence >= 0.9 else "heuristic",
                    )
                )
        return links
