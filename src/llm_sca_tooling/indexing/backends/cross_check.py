"""Cross-backend evidence agreement model."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, Severity
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode


class EvidenceAgreement(StrictBaseModel):
    fact_id: str
    fact_type: str
    contributing_backends: list[str]
    agreement: str
    merged_confidence: EvidenceStrength
    merged_derivation: DerivationType
    conflict_notes: list[str] = Field(default_factory=list)


class CrossChecker:
    def compare(
        self, facts: list[GraphNode | GraphEdge], backend_ids: list[str]
    ) -> tuple[EvidenceAgreement, list[IndexDiagnostic]]:
        unique_backends = sorted(set(backend_ids))
        diagnostics: list[IndexDiagnostic] = []
        if len(facts) > 1 and len({self._target_key(fact) for fact in facts}) > 1:
            agreement = "conflicting"
            strength = EvidenceStrength.CALIBRATED_MODEL
            diagnostics.append(
                IndexDiagnostic(
                    diagnostic_id=f"diag:cross-check:{facts[0].node_id if isinstance(facts[0], GraphNode) else facts[0].edge_id}",
                    severity=Severity.WARNING,
                    code="CROSS_CHECK_CONFLICT",
                    message="Backends produced conflicting graph facts",
                )
            )
        elif len(unique_backends) > 1:
            agreement = "confirmed"
            strength = EvidenceStrength.HARD_STATIC
        else:
            agreement = "candidate"
            strength = EvidenceStrength.STRUCTURED_REPOSITORY
        fact = facts[0]
        return (
            EvidenceAgreement(
                fact_id=fact.node_id if isinstance(fact, GraphNode) else fact.edge_id,
                fact_type=(
                    fact.node_type.value
                    if isinstance(fact, GraphNode)
                    else fact.edge_type.value
                ),
                contributing_backends=unique_backends,
                agreement=agreement,
                merged_confidence=strength,
                merged_derivation=fact.provenance.derivation,
                conflict_notes=(
                    []
                    if agreement != "conflicting"
                    else ["canonical fact keys differed"]
                ),
            ),
            diagnostics,
        )

    def _target_key(self, fact: GraphNode | GraphEdge) -> str:
        if isinstance(fact, GraphNode):
            return "|".join(
                [
                    fact.node_type.value,
                    fact.qualified_name or fact.label,
                    fact.file_path or "",
                ]
            )
        return "|".join([fact.edge_type.value, fact.source_id, fact.target_id])
