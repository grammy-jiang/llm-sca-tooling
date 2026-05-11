"""Uncertainty model for fault localisation."""

from __future__ import annotations

from llm_sca_tooling.fl.models import ConfidenceLevel, LocalisationResult

__all__ = ["apply_uncertainty"]


def apply_uncertainty(
    result: LocalisationResult,
    *,
    embedding_available: bool,
    graph_stale: bool = False,
    budget_exceeded: bool = False,
    all_frames_unresolved: bool = False,
    sarif_stale: bool = False,
) -> LocalisationResult:
    notes: list[str] = []
    confidence = result.confidence
    if result.agreement_score < 0.3:
        notes.append("Low signal agreement. Localisation may be unreliable.")
        confidence = ConfidenceLevel.heuristic
    if not embedding_available:
        notes.append(
            "Embedding retrieval unavailable. Results rely on keyword and graph "
            "signals only."
        )
    if graph_stale:
        notes.append("Graph index is stale. Candidates may miss recent changes.")
        confidence = ConfidenceLevel.heuristic
    if budget_exceeded:
        notes.append(
            "Context exceeds recommended 6-10 file budget. Candidates beyond 10 "
            "have lower confidence."
        )
    if all_frames_unresolved:
        notes.append(
            "No stack trace frames could be resolved to graph nodes. Localisation "
            "is speculative."
        )
        confidence = ConfidenceLevel.heuristic
    if sarif_stale:
        notes.append(
            "Most recent SARIF run predates current graph snapshot. SARIF prior "
            "may not reflect current code."
        )
    return result.model_copy(
        update={
            "confidence": confidence,
            "uncertainty": " ".join(notes) if notes else result.uncertainty,
        }
    )
