"""Indexing pipeline — merge, deduplicate, and write graph facts.

The merge logic is the contribution point for Phase 3: when two backends
emit the same node (same qualified name + file + type), the higher-confidence
provenance should win for canonical lookup, but both provenances should remain
traceable in the node properties.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from llm_sca_tooling.indexing.backends.base import BackendResult
from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode

__all__ = ["MergeResult", "GraphPipeline"]


@dataclass
class MergeResult:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    diagnostics: list[IndexingDiagnostic] = field(default_factory=list)
    merged_count: int = 0
    conflict_count: int = 0


def _node_key(node: GraphNode) -> str:
    """Stable identity key for deduplication: type + file + qualified_name."""
    return f"{node.node_type.value}|{node.file_path or ''}|{node.qualified_name or node.node_id}"


def _choose_stronger_provenance(a: GraphNode, b: GraphNode) -> GraphNode:
    """Return the node whose provenance has stronger evidence.

    When two backends emit the same node:
    - The node with higher evidence strength becomes canonical.
    - If equal strength, the higher confidence wins.
    - The losing node's source_tool is merged into the winner's properties.
    """
    a_strength = a.provenance.evidence_strength
    b_strength = b.provenance.evidence_strength

    if a_strength > b_strength:
        winner, loser = a, b
    elif b_strength > a_strength:
        winner, loser = b, a
    elif a.provenance.confidence >= b.provenance.confidence:
        winner, loser = a, b
    else:
        winner, loser = b, a

    # Merge the loser's source_tool into winner's properties for auditability
    merged_props = dict(winner.properties)
    raw_merged_provenances = merged_props.get("merged_provenances", [])
    merged_provenances = (
        list(raw_merged_provenances) if isinstance(raw_merged_provenances, list) else []
    )
    merged_provenances.append(loser.provenance.source_tool)
    merged_props["merged_provenances"] = merged_provenances

    return winner.model_copy(update={"properties": merged_props})


class GraphPipeline:
    """Merge backend results and prepare deduplicated graph facts."""

    def merge(self, results: list[BackendResult]) -> MergeResult:
        """Merge outputs from multiple backends into a single deduplicated set."""
        merged = MergeResult()
        node_registry: dict[str, GraphNode] = {}
        edge_keys: set[str] = set()

        for backend_result in results:
            merged.diagnostics.extend(backend_result.diagnostics)

            for node in backend_result.nodes:
                key = _node_key(node)
                if key in node_registry:
                    existing = node_registry[key]
                    if existing.node_id != node.node_id:
                        # Span conflict check
                        if existing.span != node.span and existing.span and node.span:
                            merged.diagnostics.append(
                                IndexingDiagnostic(
                                    severity=DiagnosticSeverity.info,
                                    code="MERGE_SPAN_CONFLICT",
                                    message=f"Conflicting spans for {key}",
                                    file_path=node.file_path,
                                    backend_id=node.provenance.source_tool,
                                )
                            )
                            merged.conflict_count += 1
                        node_registry[key] = _choose_stronger_provenance(existing, node)
                        merged.merged_count += 1
                else:
                    node_registry[key] = node

            for edge in backend_result.edges:
                edge_key = f"{edge.edge_type.value}|{edge.source_id}|{edge.target_id}"
                if edge_key not in edge_keys:
                    edge_keys.add(edge_key)
                    merged.edges.append(edge)

        merged.nodes = list(node_registry.values())
        return merged
