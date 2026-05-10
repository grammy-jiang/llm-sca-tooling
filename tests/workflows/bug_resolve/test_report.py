"""Tests for the report assembler / verdict rules."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import (
    CandidatePatch,
    CertificateConclusion,
    FinalVerdict,
    GateRunnerResult,
    MonitorEvent,
    MonitorType,
    RecommendationValue,
    StageName,
    StatusValue,
    WorkflowState,
)
from llm_sca_tooling.workflows.bug_resolve.report import (
    assemble_report,
    compute_final_verdict,
)


def _state_with_pass(idx: int = 0) -> WorkflowState:
    s = WorkflowState(run_id="r1")
    s.status = StatusValue.RUNNING
    s.selected_patch = CandidatePatch(run_id="r1", candidate_index=idx)
    s.gate_results = [
        GateRunnerResult(
            run_id="r1",
            candidate_index=idx,
            sarif_gate_pass=True,
            overall_gate_pass=True,
            certificate_conclusion=CertificateConclusion.SUPPORTED,
        )
    ]
    return s


def test_resolved_merge_supporting() -> None:
    s = _state_with_pass()
    v, r = compute_final_verdict(
        state=s, process_compliant=True, selected_index=0, uncertainty=[]
    )
    assert v is FinalVerdict.RESOLVED
    assert r is RecommendationValue.MERGE_SUPPORTING


def test_budget_exhausted_blocks() -> None:
    s = WorkflowState(run_id="r1")
    s.status = StatusValue.BUDGET_EXHAUSTED
    v, r = compute_final_verdict(
        state=s, process_compliant=False, selected_index=None, uncertainty=[]
    )
    assert v is FinalVerdict.BUDGET_EXHAUSTED
    assert r is RecommendationValue.BLOCK


def test_process_noncompliant_blocks() -> None:
    s = WorkflowState(run_id="r1")
    v, r = compute_final_verdict(
        state=s, process_compliant=False, selected_index=0, uncertainty=[]
    )
    assert v is FinalVerdict.PROCESS_NONCOMPLIANT
    assert r is RecommendationValue.BLOCK


def test_no_fix_found_blocks() -> None:
    s = WorkflowState(run_id="r1")
    s.status = StatusValue.COMPLETED_NO_FIX
    v, r = compute_final_verdict(
        state=s, process_compliant=True, selected_index=None, uncertainty=[]
    )
    assert v is FinalVerdict.NO_FIX_FOUND
    assert r is RecommendationValue.BLOCK


def test_uncertain_review() -> None:
    s = WorkflowState(run_id="r1")
    s.status = StatusValue.COMPLETED_UNCERTAIN
    v, r = compute_final_verdict(
        state=s, process_compliant=True, selected_index=0, uncertainty=[]
    )
    assert v is FinalVerdict.UNCERTAIN
    assert r is RecommendationValue.REVIEW_REQUIRED


def test_certificate_unsupported_review() -> None:
    s = _state_with_pass()
    s.gate_results[0] = GateRunnerResult(
        run_id="r1",
        candidate_index=0,
        sarif_gate_pass=True,
        overall_gate_pass=True,
        certificate_conclusion=CertificateConclusion.UNSUPPORTED,
    )
    v, r = compute_final_verdict(
        state=s, process_compliant=True, selected_index=0, uncertainty=[]
    )
    assert v is FinalVerdict.RESOLVED_WITH_RISK
    assert r is RecommendationValue.REVIEW_REQUIRED


def test_uncertainty_downgrades_to_review() -> None:
    s = _state_with_pass()
    v, r = compute_final_verdict(
        state=s,
        process_compliant=True,
        selected_index=0,
        uncertainty=["stale_snapshot:foo"],
    )
    assert v is FinalVerdict.RESOLVED_WITH_RISK
    assert r is RecommendationValue.REVIEW_REQUIRED


def test_assemble_report_fields() -> None:
    s = _state_with_pass()
    s.status = StatusValue.COMPLETED_SUCCESS
    rep = assemble_report(
        state=s,
        issue_text_hash="h",
        harness_condition_id="hcs:1",
        process_compliant=True,
        operational_verdict="ok",
    )
    assert rep.harness_condition_id == "hcs:1"
    assert rep.recommendation is RecommendationValue.MERGE_SUPPORTING


def test_assemble_report_stale_snapshot_uncertainty() -> None:
    s = _state_with_pass()
    s.status = StatusValue.COMPLETED_SUCCESS
    s.monitor_events.append(
        MonitorEvent(
            run_id="r1",
            monitor_type=MonitorType.STALE_SNAPSHOT_DETECTED_BEFORE_FINAL_REPORT,
            stage=StageName.TRAJECTORY,
            detail="snap mismatch",
        )
    )
    rep = assemble_report(
        state=s,
        issue_text_hash="h",
        harness_condition_id="hcs:1",
        process_compliant=True,
        operational_verdict="ok",
    )
    assert any("stale_snapshot" in u for u in rep.uncertainty)


def test_assemble_report_dryrun_mismatches_count() -> None:
    s = _state_with_pass()
    s.status = StatusValue.COMPLETED_SUCCESS
    rep = assemble_report(
        state=s,
        issue_text_hash="h",
        harness_condition_id="hcs:1",
        process_compliant=True,
        operational_verdict="ok",
        dryrun_mismatches_ref=["m1", "m2"],
    )
    assert any("dryrun_mismatches_count=2" in u for u in rep.uncertainty)
