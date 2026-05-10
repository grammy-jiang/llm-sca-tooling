"""Patch selection policy for the bug-resolve workflow."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.workflows.bug_resolve.models import (
    CandidatePatch,
    GateRunnerResult,
    PatchSelectionRecord,
)

SELECTION_CRITERIA = (
    "agreement_score_desc",
    "changed_graph_nodes_asc",
    "patch_risk_probability_asc",
    "no_new_sarif_alerts",
    "reproduction_test_or_poc_survival",
)


def _risk_probability(risk_result: dict[str, Any] | None) -> float:
    if not risk_result:
        return 1.0
    prob = risk_result.get("calibrated_probability")
    if isinstance(prob, (int, float)):
        return float(prob)
    return 1.0


def select_patch(
    *,
    run_id: str,
    candidates: list[CandidatePatch],
    gate_results: list[GateRunnerResult],
    risk_results: list[dict[str, Any]] | None = None,
    agreement_score: float = 0.0,
) -> PatchSelectionRecord:
    """Multi-criterion patch selection.

    Only candidates whose paired :class:`GateRunnerResult` has
    ``overall_gate_pass: True`` are eligible for selection.
    """
    risk_results = list(risk_results or [])
    rejected: list[int] = []
    rejection_reasons: list[str] = []

    eligible: list[tuple[CandidatePatch, GateRunnerResult, dict[str, Any] | None]] = []
    for candidate, gate in zip(candidates, gate_results, strict=False):
        risk = (
            risk_results[candidate.candidate_index]
            if candidate.candidate_index < len(risk_results)
            else None
        )
        if not gate.overall_gate_pass:
            rejected.append(candidate.candidate_index)
            rejection_reasons.append("; ".join(gate.block_reasons) or "gate_failed")
            continue
        eligible.append((candidate, gate, risk))

    if not eligible:
        return PatchSelectionRecord(
            run_id=run_id,
            candidates_evaluated=len(candidates),
            selected_candidate_index=None,
            selection_rationale="no candidate passed all hard gates",
            selection_criteria=list(SELECTION_CRITERIA),
            rejected_candidates=rejected,
            rejection_reasons=rejection_reasons,
        )

    def sort_key(
        item: tuple[CandidatePatch, GateRunnerResult, dict[str, Any] | None],
    ) -> tuple[float, int, float, int]:
        candidate, gate, risk = item
        # Higher agreement score first → invert.
        # Fewer changed graph nodes first.
        # Lower risk probability first.
        # SARIF cleanliness preferred — sarif_gate_pass=True ranks lower.
        sarif_penalty = 0 if gate.sarif_gate_pass else 1
        return (
            -float(agreement_score),
            len(candidate.changed_symbol_ids) + len(candidate.changed_files),
            _risk_probability(risk),
            sarif_penalty,
        )

    eligible.sort(key=sort_key)
    chosen, _gate, _risk = eligible[0]
    rationale = "selected by agreement score, smaller blast radius, lower risk"
    return PatchSelectionRecord(
        run_id=run_id,
        candidates_evaluated=len(candidates),
        selected_candidate_index=chosen.candidate_index,
        selection_rationale=rationale,
        selection_criteria=list(SELECTION_CRITERIA),
        rejected_candidates=rejected,
        rejection_reasons=rejection_reasons,
    )


__all__ = ["select_patch", "SELECTION_CRITERIA"]
