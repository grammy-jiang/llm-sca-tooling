"""Deterministic fact reconciliation."""

from __future__ import annotations

from collections import defaultdict

from llm_sca_tooling.indexing.backends.base import BackendResult
from llm_sca_tooling.indexing.backends.cross_check import CrossChecker, EvidenceAgreement
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode


class FactReconciliationResult:
    def __init__(self, nodes: list[GraphNode], edges: list[GraphEdge], agreements: list[EvidenceAgreement], diagnostics: list[IndexDiagnostic]) -> None:
        self.nodes = nodes
        self.edges = edges
        self.agreements = agreements
        self.diagnostics = diagnostics


class FactReconciler:
    def __init__(self) -> None:
        self.cross_checker = CrossChecker()

    def reconcile(self, results: list[BackendResult]) -> FactReconciliationResult:
        node_groups: dict[str, list[tuple[GraphNode, str]]] = defaultdict(list)
        edge_groups: dict[str, list[tuple[GraphEdge, str]]] = defaultdict(list)
        for result in results:
            for node in result.nodes:
                node_groups[_node_key(node)].append((node, result.backend_id))
            for edge in result.edges:
                edge_groups[_edge_key(edge)].append((edge, result.backend_id))
        nodes, edges, agreements, diagnostics = [], [], [], []
        node_id_remap: dict[str, str] = {}
        for group in node_groups.values():
            facts = [item[0] for item in group]
            agreement, diag = self.cross_checker.compare(facts, [item[1] for item in group])
            node = facts[0].model_copy(deep=True)
            for fact in facts:
                node_id_remap[fact.node_id] = node.node_id
            node.properties = {**node.properties, "evidence_agreement": agreement.model_dump(mode="json")}
            nodes.append(node)
            agreements.append(agreement)
            diagnostics.extend(diag)
        remapped_edge_groups: dict[str, list[tuple[GraphEdge, str]]] = defaultdict(list)
        for group in edge_groups.values():
            for edge, backend_id in group:
                source_id = node_id_remap.get(edge.source_id, edge.source_id)
                target_id = node_id_remap.get(edge.target_id, edge.target_id)
                if source_id == target_id:
                    continue
                clone = GraphEdge.model_validate(
                    {**edge.model_dump(mode="python"), "source_id": source_id, "target_id": target_id}
                )
                remapped_edge_groups[_edge_key(clone)].append((clone, backend_id))
        for group in remapped_edge_groups.values():
            facts = [item[0] for item in group]
            agreement, diag = self.cross_checker.compare(facts, [item[1] for item in group])
            if agreement.agreement == "conflicting":
                for fact, _backend in group:
                    edge = fact.model_copy(deep=True)
                    edge.confidence = min(edge.confidence, 0.4)
                    edge.properties = {**edge.properties, "evidence_agreement": agreement.model_dump(mode="json")}
                    edges.append(edge)
            else:
                edge = facts[0].model_copy(deep=True)
                edge.properties = {**edge.properties, "evidence_agreement": agreement.model_dump(mode="json")}
                edges.append(edge)
            agreements.append(agreement)
            diagnostics.extend(diag)
        return FactReconciliationResult(nodes=nodes, edges=edges, agreements=agreements, diagnostics=diagnostics)


def _node_key(node: GraphNode) -> str:
    return "|".join([node.node_type.value, node.qualified_name or node.label, node.file_path or ""])


def _edge_key(edge: GraphEdge) -> str:
    return "|".join([edge.edge_type.value, edge.source_id, edge.target_id])
