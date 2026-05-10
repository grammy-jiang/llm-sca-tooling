"""Uncertainty model for fault-localisation results."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.fl.models import (
    ConfidenceLevel,
    ContextBundle,
    RetrievalDiagnostic,
    SignalType,
)
from llm_sca_tooling.schemas.base import StrictBaseModel


class UncertaintyAssessment(StrictBaseModel):
    messages: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel
    diagnostics: list[RetrievalDiagnostic] = Field(default_factory=list)

    @property
    def uncertainty(self) -> str | None:
        return " ".join(self.messages) if self.messages else None


class UncertaintyModel:
    def evaluate(
        self,
        *,
        agreement_score: float,
        base_confidence: ConfidenceLevel,
        issue: IssueText,
        context_bundle: ContextBundle | None,
        signals_missing: list[SignalType],
        diagnostics: list[RetrievalDiagnostic],
        stack_frames_resolved: bool,
    ) -> UncertaintyAssessment:
        messages: list[str] = []
        confidence = base_confidence
        available_count = len(SignalType) - len(signals_missing)
        if agreement_score < 0.3:
            messages.append(
                f"Low signal agreement. Only {max(0, round(agreement_score * max(available_count, 1)))} of {max(available_count, 1)} signals contributed. Localisation may be unreliable."
            )
            confidence = _downgrade(confidence)
        if SignalType.EMBEDDING in signals_missing:
            messages.append(
                "Embedding retrieval unavailable. Results rely on keyword and graph signals only."
            )
            confidence = _downgrade(confidence)
        if context_bundle and context_bundle.is_over_budget:
            messages.append(
                "Context exceeds recommended 6-10 file budget. Candidates beyond 10 have lower confidence."
            )
            confidence = _downgrade(confidence)
        if issue.stack_trace_frames and not stack_frames_resolved:
            messages.append(
                "No stack trace frames could be resolved to graph nodes. Localisation is speculative."
            )
            confidence = ConfidenceLevel.HEURISTIC
        for diagnostic in diagnostics:
            if diagnostic.code == "SARIF_STALE":
                messages.append(
                    "Most recent SARIF run predates current graph snapshot. SARIF prior may not reflect current code."
                )
            elif diagnostic.code == "GRAPH_STALE":
                messages.append(
                    "Graph index is stale. Candidates may miss recent changes."
                )
                confidence = ConfidenceLevel.HEURISTIC
            elif diagnostic.code == "MEMORY_HINT_REJECTED":
                messages.append(
                    "Memory hints were filtered by the misalignment guard. Trajectory data not used."
                )
        return UncertaintyAssessment(
            messages=list(dict.fromkeys(messages)),
            confidence=confidence,
            diagnostics=diagnostics,
        )


def _downgrade(confidence: ConfidenceLevel) -> ConfidenceLevel:
    if confidence == ConfidenceLevel.ANALYSER:
        return ConfidenceLevel.HEURISTIC
    if confidence == ConfidenceLevel.PARSER:
        return ConfidenceLevel.ANALYSER
    return confidence
