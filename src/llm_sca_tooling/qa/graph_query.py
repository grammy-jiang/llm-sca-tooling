"""Graph-path answer building for repository QA."""

from __future__ import annotations

from collections import deque

from pydantic import Field

from llm_sca_tooling.qa.confidence import ConfidenceLabel, confidence_from_float, min_confidence
from llm_sca_tooling.qa.lookup import GraphNodeRef, node_ref
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import GraphEdgeType
from llm_sca_tooling.schemas.provenance import ArtifactRef, SourceSpan
from llm_sca_tooling.storage.graph_queries import GraphSlice
from llm_sca_tooling.storage.graph_store import GraphStore


class GraphEdgeRef(StrictBaseModel):
    edge_id: str
    edge_type: str
    source_id: str
    target_id: str
    confidence: ConfidenceLabel


class GraphPath(StrictBaseModel):
    path_id: str
    nodes: list[GraphNodeRef]
    edges: list[GraphEdgeRef]
    start_node_id: str
    end_node_id: str
    hop_count: int
    confidence: ConfidenceLabel
    snippet_refs: list[ArtifactRef] = Field(default_factory=list)


class DocumentLink(StrictBaseModel):
    doc_node_id: str
    doc_file_path: str | None = None
    doc_span: SourceSpan | None = None
    code_node_id: str
    code_file_path: str | None = None
    code_span: SourceSpan | None = None
    edge_type: str
    confidence: ConfidenceLabel


class GraphPathBuilder:
    def __init__(self, graph_store: GraphStore) -> None:
        self.graph = graph_store

    def build_path(self, start_node_id: str, end_node_id: str | None = None, edge_types: list[str] | None = None, max_depth: int = 4) -> list[GraphPath]:
        allowed = set(edge_types or [])
        queue = deque([(start_node_id, [])])
        seen = {start_node_id}
        found: list[GraphPath] = []
        while queue:
            node_id, edge_ids = queue.popleft()
            if len(edge_ids) >= max_depth:
                continue
            for row in self._adjacent_edges(node_id, allowed):
                edge_id = row["edge_id"]
                next_id = row["target_id"] if row["source_id"] == node_id else row["source_id"]
                if next_id in seen and next_id != end_node_id:
                    continue
                next_edges = [*edge_ids, edge_id]
                if end_node_id is None or next_id == end_node_id:
                    path = self._path_from_edges(start_node_id, next_id, next_edges)
                    if path:
                        found.append(path)
                    if end_node_id is not None:
                        continue
                seen.add(next_id)
                queue.append((next_id, next_edges))
        return sorted(found, key=lambda path: path.hop_count)

    def build_ego_graph(self, node_id: str, edge_types: list[str] | None = None, depth: int = 1) -> GraphSlice:
        parsed = [GraphEdgeType(edge_type) for edge_type in edge_types or []]
        return self.graph.fetch_ego_graph([node_id], depth=depth, edge_types=parsed or None)

    def find_document_links(self, node_id: str) -> list[DocumentLink]:
        rows = self.graph.conn.execute(
            "SELECT payload_json FROM graph_edges WHERE (source_id=? OR target_id=?) AND edge_type IN ('documents','checks','satisfies')",
            (node_id, node_id),
        ).fetchall()
        links = []
        for row in rows:
            edge = self.graph.fetch_edge(__import__("json").loads(row["payload_json"])["edge_id"])
            if edge is None:
                continue
            source = self.graph.fetch_node(edge.source_id)
            target = self.graph.fetch_node(edge.target_id)
            if source is None or target is None:
                continue
            doc, code = (source, target) if source.node_type.value in {"document", "design_clause"} else (target, source)
            links.append(
                DocumentLink(
                    doc_node_id=doc.node_id,
                    doc_file_path=doc.file_path,
                    doc_span=doc.span,
                    code_node_id=code.node_id,
                    code_file_path=code.file_path,
                    code_span=code.span,
                    edge_type=edge.edge_type.value,
                    confidence=confidence_from_float(edge.confidence),
                )
            )
        return links

    def _adjacent_edges(self, node_id: str, allowed: set[str]):
        if allowed:
            return self.graph.conn.execute(
                f"SELECT edge_id, source_id, target_id FROM graph_edges WHERE (source_id=? OR target_id=?) AND edge_type IN ({','.join('?' for _ in allowed)})",
                (node_id, node_id, *allowed),
            ).fetchall()
        return self.graph.conn.execute("SELECT edge_id, source_id, target_id FROM graph_edges WHERE source_id=? OR target_id=?", (node_id, node_id)).fetchall()

    def _path_from_edges(self, start_node_id: str, end_node_id: str, edge_ids: list[str]) -> GraphPath | None:
        edges = [self.graph.fetch_edge(edge_id) for edge_id in edge_ids]
        edges = [edge for edge in edges if edge is not None]
        if len(edges) != len(edge_ids):
            return None
        node_ids = {start_node_id, end_node_id}
        for edge in edges:
            node_ids.add(edge.source_id)
            node_ids.add(edge.target_id)
        nodes = [self.graph.fetch_node(node_id) for node_id in node_ids]
        nodes = [node for node in nodes if node is not None]
        edge_refs = [GraphEdgeRef(edge_id=edge.edge_id, edge_type=edge.edge_type.value, source_id=edge.source_id, target_id=edge.target_id, confidence=confidence_from_float(edge.confidence)) for edge in edges]
        return GraphPath(
            path_id=f"path:{start_node_id}:{end_node_id}:{':'.join(edge_ids)}",
            nodes=[node_ref(node, confidence_from_float(node.provenance.confidence), "graph_path") for node in nodes],
            edges=edge_refs,
            start_node_id=start_node_id,
            end_node_id=end_node_id,
            hop_count=len(edges),
            confidence=min_confidence([edge.confidence for edge in edge_refs]),
        )
