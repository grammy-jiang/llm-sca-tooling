"""BugResolveReport assembler with verdict and recommendation rules."""

from __future__ import annotations

import hashlib

from llm_sca_tooling.evaluation.models import utc_now_ts
from llm_sca_tooling.workflows.bug_resolve.models import (
    BugResolveReport,
    CertificateConclusion,
    FinalVerdict,
    GateRunnerResult,
    RecommendationValue,
    StatusValue,
    WorkflowState,
)


def _report_id(run_id: str) -> str:
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:24]
    return f"bug-resolve-report:{digest}"


def _has_remaining_risk(
    gates: list[GateRunnerResult],
    selected_index: int | None,
    uncertainty: list[str],
) -> bool:
    if uncertainty:
        return True
    if selected_index is None:
        return False
    for gate in gates:
        if gate.candidate_index == selected_index:
            if gate.certificate_conclusion in (
                CertificateConclusion.PARTIALLY_SUPPORTED,
                CertificateConclusion.UNKNOWN,
            ):
                return True
            if gate.block_reasons:
                return True
    return False


def compute_final_verdict(
    *,
    state: WorkflowState,
    process_compliant: bool,
    selected_index: int | None,
    uncertainty: list[str],
) -> tuple[FinalVerdict, RecommendationValue]:
    """Apply Phase 13 verdict / recommendation rules."""
    if state.status is StatusValue.BUDGET_EXHAUSTED:
        return FinalVerdict.BUDGET_EXHAUSTED, RecommendationValue.BLOCK
    if not process_compliant:
        return FinalVerdict.PROCESS_NONCOMPLIANT, RecommendationValue.BLOCK
    if state.status is StatusValue.FAILED:
        return FinalVerdict.NO_FIX_FOUND, RecommendationValue.BLOCK
    if state.status is StatusValue.COMPLETED_NO_FIX or selected_index is None:
        return FinalVerdict.NO_FIX_FOUND, RecommendationValue.BLOCK
    if state.status is StatusValue.COMPLETED_UNCERTAIN:
        return FinalVerdict.UNCERTAIN, RecommendationValue.REVIEW_REQUIRED

    selected_gate = next(
        (g for g in state.gate_results if g.candidate_index == selected_index),
        None,
    )
    if selected_gate is None or not selected_gate.overall_gate_pass:
        return FinalVerdict.NO_FIX_FOUND, RecommendationValue.BLOCK

    if selected_gate.certificate_conclusion is CertificateConclusion.UNSUPPORTED:
        # Soft block — recommendation downgraded.
        return FinalVerdict.RESOLVED_WITH_RISK, RecommendationValue.REVIEW_REQUIRED

    if _has_remaining_risk(state.gate_results, selected_index, uncertainty):
        return FinalVerdict.RESOLVED_WITH_RISK, RecommendationValue.REVIEW_REQUIRED

    return FinalVerdict.RESOLVED, RecommendationValue.MERGE_SUPPORTING


def assemble_report(
    *,
    state: WorkflowState,
    issue_text_hash: str,
    harness_condition_id: str,
    process_compliant: bool,
    operational_verdict: str,
    incident_links: list[str] | None = None,
    uncertainty: list[str] | None = None,
    investigate_result_ref: str | None = None,
    selected_patch_ref: str | None = None,
    candidate_patches_ref: list[str] | None = None,
    precondition_draft_ref: str | None = None,
    postcondition_draft_ref: str | None = None,
    reproduction_tests_ref: list[str] | None = None,
    certificate_ref: str | None = None,
    gate_results_ref: list[str] | None = None,
    patch_risk_result_ref: str | None = None,
    blast_radius_result_ref: str | None = None,
    scope_audit_result_ref: str | None = None,
    patch_review_report_ref: str | None = None,
    dryrun_prediction_ref: str | None = None,
    dryrun_mismatches_ref: list[str] | None = None,
    session_trace_manifest_ref: str | None = None,
) -> BugResolveReport:
    """Assemble the final :class:`BugResolveReport`."""
    selected_index = (
        state.selected_patch.candidate_index if state.selected_patch else None
    )
    notes = list(uncertainty or [])
    # Add stale-snapshot note from monitor events.
    for event in state.monitor_events:
        if event.monitor_type.value == "stale_snapshot_detected_before_final_report":
            notes.append(f"stale_snapshot:{event.detail}")
    # Add DryRUN mismatch summary if any.
    if dryrun_mismatches_ref:
        notes.append(f"dryrun_mismatches_count={len(dryrun_mismatches_ref)}")

    verdict, recommendation = compute_final_verdict(
        state=state,
        process_compliant=process_compliant,
        selected_index=selected_index,
        uncertainty=notes,
    )

    return BugResolveReport(
        report_id=_report_id(state.run_id),
        run_id=state.run_id,
        harness_condition_id=harness_condition_id,
        issue_text_hash=issue_text_hash,
        investigate_result_ref=investigate_result_ref,
        selected_patch_ref=selected_patch_ref,
        candidate_patches_ref=list(candidate_patches_ref or []),
        precondition_draft_ref=precondition_draft_ref,
        postcondition_draft_ref=postcondition_draft_ref,
        reproduction_tests_ref=list(reproduction_tests_ref or []),
        certificate_ref=certificate_ref,
        gate_results_ref=list(gate_results_ref or []),
        patch_risk_result_ref=patch_risk_result_ref,
        blast_radius_result_ref=blast_radius_result_ref,
        scope_audit_result_ref=scope_audit_result_ref,
        patch_review_report_ref=patch_review_report_ref,
        dryrun_prediction_ref=dryrun_prediction_ref,
        dryrun_mismatches_ref=list(dryrun_mismatches_ref or []),
        operational_verdict=operational_verdict,
        incident_links=list(incident_links or []),
        final_verdict=verdict,
        recommendation=recommendation,
        uncertainty=notes,
        session_trace_manifest_ref=session_trace_manifest_ref,
        created_ts=utc_now_ts(),
    )


__all__ = ["assemble_report", "compute_final_verdict"]
