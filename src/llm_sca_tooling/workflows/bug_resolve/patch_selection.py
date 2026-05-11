"""Patch selection policy."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import (
    CandidatePatch,
    GateRunnerResult,
    InvestigateResult,
    PatchSelectionRecord,
)


def select_patch(
    *,
    run_id: str,
    patches: list[CandidatePatch],
    gate_results: list[GateRunnerResult],
    investigate: InvestigateResult,
) -> PatchSelectionRecord:
    passing = [
        (patch, gate)
        for patch, gate in zip(patches, gate_results, strict=True)
        if gate.overall_gate_pass
    ]
    rejection_reasons = [
        f"candidate_{g.candidate_index}: {','.join(g.block_reasons)}"
        for g in gate_results
        if not g.overall_gate_pass
    ]

    if not passing:
        return PatchSelectionRecord(
            run_id=run_id,
            candidates_evaluated=len(patches),
            selected_candidate_index=None,
            selection_rationale="no_candidate_passed_all_gates",
            rejected_candidates=list(range(len(patches))),
            rejection_reasons=rejection_reasons,
        )

    # Select by fewest changed files then agreement score
    best_patch, _best_gate = min(
        passing,
        key=lambda pg: (len(pg[0].changed_files), -investigate.agreement_score),
    )
    return PatchSelectionRecord(
        run_id=run_id,
        candidates_evaluated=len(patches),
        selected_candidate_index=best_patch.candidate_index,
        selection_rationale="fewest_changed_files_and_agreement_score",
        selection_criteria=["fewest_changed_graph_nodes", "agreement_score"],
        rejected_candidates=[
            p.candidate_index for p, _ in passing if p is not best_patch
        ],
        rejection_reasons=[],
    )
