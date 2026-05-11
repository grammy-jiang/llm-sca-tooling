"""Cross-backend evidence agreement and fact reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from llm_sca_tooling.indexing.backends.base import BackendResult
from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode

__all__ = ["EvidenceAgreement", "FactReconciler", "ReconciledFacts"]

AgreementState = Literal["confirmed", "candidate", "conflicting"]


@dataclass(frozen=True)
class EvidenceAgreement:
    fact_id: str
    fact_type: str
    contributing_backends: list[str]
    agreement: AgreementState
    merged_confidence: float
    conflict_notes: list[str] = field(default_factory=list)


@dataclass
class ReconciledFacts:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    agreements: list[EvidenceAgreement]
    diagnostics: list[IndexingDiagnostic]


class FactReconciler:
    """Deterministically reconcile overlapping backend facts."""

    def reconcile(self, results: list[BackendResult]) -> ReconciledFacts:
        nodes_by_key: dict[str, list[tuple[str, GraphNode]]] = {}
        edges_by_key: dict[str, list[tuple[str, GraphEdge]]] = {}
        diagnostics: list[IndexingDiagnostic] = []
        for result in results:
            diagnostics.extend(result.diagnostics)
            for node in result.nodes:
                nodes_by_key.setdefault(_node_key(node), []).append(
                    (result.backend_id, node)
                )
            for edge in result.edges:
                edges_by_key.setdefault(_edge_key(edge), []).append(
                    (result.backend_id, edge)
                )

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        agreements: list[EvidenceAgreement] = []
        for fact_key, node_group in sorted(nodes_by_key.items()):
            contributors = sorted({backend for backend, _ in node_group})
            node = max(node_group, key=lambda item: item[1].provenance.confidence)[1]
            nodes.append(_annotate_node(node, contributors))
            agreements.append(
                EvidenceAgreement(
                    fact_id=fact_key,
                    fact_type="node",
                    contributing_backends=contributors,
                    agreement="confirmed" if len(contributors) > 1 else "candidate",
                    merged_confidence=node.provenance.confidence,
                )
            )

        for fact_key, edge_group in sorted(edges_by_key.items()):
            contributors = sorted({backend for backend, _ in edge_group})
            target_ids = {edge.target_id for _, edge in edge_group}
            if len(target_ids) > 1:
                for _, edge in edge_group:
                    edges.append(_annotate_edge(edge, contributors, "conflicting"))
                diagnostics.append(
                    IndexingDiagnostic(
                        severity=DiagnosticSeverity.warning,
                        code="CROSS_CHECK_CONFLICT",
                        message=f"conflicting edge targets for {fact_key}",
                    )
                )
                agreements.append(
                    EvidenceAgreement(
                        fact_id=fact_key,
                        fact_type="edge",
                        contributing_backends=contributors,
                        agreement="conflicting",
                        merged_confidence=min(
                            edge.provenance.confidence for _, edge in edge_group
                        ),
                        conflict_notes=sorted(target_ids),
                    )
                )
                continue

            edge = max(edge_group, key=lambda item: item[1].provenance.confidence)[1]
            agreement: AgreementState = (
                "confirmed" if len(contributors) > 1 else "candidate"
            )
            edges.append(_annotate_edge(edge, contributors, agreement))
            agreements.append(
                EvidenceAgreement(
                    fact_id=fact_key,
                    fact_type="edge",
                    contributing_backends=contributors,
                    agreement=agreement,
                    merged_confidence=edge.provenance.confidence,
                )
            )

        return ReconciledFacts(nodes, edges, agreements, diagnostics)


def _node_key(node: GraphNode) -> str:
    return f"{node.node_type.value}|{node.file_path or ''}|{node.qualified_name or node.label}"


def _edge_key(edge: GraphEdge) -> str:
    return f"{edge.edge_type.value}|{edge.source_id}"


def _annotate_node(node: GraphNode, backends: list[str]) -> GraphNode:
    props = dict(node.properties)
    props["contributing_backends"] = backends
    props["agreement"] = "confirmed" if len(backends) > 1 else "candidate"
    return node.model_copy(update={"properties": props})


def _annotate_edge(
    edge: GraphEdge, backends: list[str], agreement: AgreementState
) -> GraphEdge:
    props = dict(edge.properties)
    props["contributing_backends"] = backends
    props["agreement"] = agreement
    return edge.model_copy(update={"properties": props})
