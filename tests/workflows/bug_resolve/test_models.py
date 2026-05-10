"""Tests for Phase 13 bug-resolve Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.workflows.bug_resolve.models import (
    BlastRadiusStub,
    BugResolveReport,
    CandidatePatch,
    CertificateConclusion,
    ExecutionFreeCertificate,
    FinalVerdict,
    GateRunnerResult,
    InvestigateResult,
    MonitorEvent,
    MonitorType,
    PatchSelectionRecord,
    PrePostConditionDraft,
    RecommendationValue,
    RepairContextRecord,
    ReproductionTestRecord,
    SessionTraceManifest,
    StageName,
    StatusValue,
    TestExecResult,
    WorkflowState,
)


def test_stage_name_exhaustive() -> None:
    assert {s.value for s in StageName} == {
        "load",
        "investigate",
        "repair",
        "dryrun",
        "gates",
        "patch_risk",
        "blast_radius",
        "scope_audit",
        "operational_review",
        "trajectory",
    }


def test_status_value_exhaustive() -> None:
    assert "completed_success" in {s.value for s in StatusValue}
    assert "budget_exhausted" in {s.value for s in StatusValue}


def test_final_verdict_exhaustive() -> None:
    assert {v.value for v in FinalVerdict} == {
        "resolved",
        "resolved_with_risk",
        "no_fix_found",
        "uncertain",
        "process_noncompliant",
        "budget_exhausted",
    }


def test_recommendation_exhaustive() -> None:
    assert {r.value for r in RecommendationValue} == {
        "merge-supporting",
        "review-required",
        "block",
        "unknown",
    }


def test_investigate_result_roundtrip() -> None:
    ir = InvestigateResult(run_id="r1", issue_text_hash="h1")
    data = ir.model_dump_json()
    rt = InvestigateResult.model_validate_json(data)
    assert rt == ir


def test_candidate_patch_roundtrip() -> None:
    cp = CandidatePatch(run_id="r1", candidate_index=0)
    rt = CandidatePatch.model_validate_json(cp.model_dump_json())
    assert rt.run_id == "r1"


def test_repair_context_record_roundtrip() -> None:
    r = RepairContextRecord(run_id="r1", candidate_index=0)
    rt = RepairContextRecord.model_validate_json(r.model_dump_json())
    assert rt == r


def test_prepost_draft_roundtrip() -> None:
    d = PrePostConditionDraft(run_id="r1", candidate_index=0, function_path="x.py:foo")
    rt = PrePostConditionDraft.model_validate_json(d.model_dump_json())
    assert rt == d


def test_reproduction_test_record_roundtrip() -> None:
    rec = ReproductionTestRecord(run_id="r1", candidate_index=0)
    rt = ReproductionTestRecord.model_validate_json(rec.model_dump_json())
    assert rt == rec


def test_certificate_roundtrip() -> None:
    c = ExecutionFreeCertificate(run_id="r1", candidate_index=0)
    rt = ExecutionFreeCertificate.model_validate_json(c.model_dump_json())
    assert rt.conclusion is CertificateConclusion.UNKNOWN


def test_gate_runner_result_roundtrip() -> None:
    g = GateRunnerResult(run_id="r1", candidate_index=0)
    rt = GateRunnerResult.model_validate_json(g.model_dump_json())
    assert rt.required_test_result is TestExecResult.NOT_EXECUTED


def test_patch_selection_roundtrip() -> None:
    p = PatchSelectionRecord(run_id="r1")
    rt = PatchSelectionRecord.model_validate_json(p.model_dump_json())
    assert rt == p


def test_blast_radius_stub_default_partial() -> None:
    b = BlastRadiusStub(run_id="r1", candidate_index=0)
    assert b.is_partial is True


def test_monitor_event_roundtrip() -> None:
    e = MonitorEvent(
        run_id="r1",
        monitor_type=MonitorType.DOOM_LOOP_CANDIDATE,
        stage=StageName.REPAIR,
    )
    rt = MonitorEvent.model_validate_json(e.model_dump_json())
    assert rt == e


def test_workflow_state_defaults() -> None:
    s = WorkflowState(run_id="r1")
    assert s.stage is StageName.LOAD
    assert s.status is StatusValue.RUNNING


def test_bug_resolve_report_required_fields() -> None:
    rep = BugResolveReport(
        report_id="bug-resolve-report:abc",
        run_id="r1",
        harness_condition_id="hcs:1",
        issue_text_hash="h1",
        final_verdict=FinalVerdict.RESOLVED,
        recommendation=RecommendationValue.MERGE_SUPPORTING,
        created_ts="2024-01-01T00:00:00Z",
    )
    assert rep.final_verdict is FinalVerdict.RESOLVED


def test_bug_resolve_report_missing_required_fails() -> None:
    with pytest.raises(ValidationError):
        BugResolveReport(  # type: ignore[call-arg]
            run_id="r1",
            harness_condition_id="hcs:1",
            issue_text_hash="h1",
            final_verdict=FinalVerdict.RESOLVED,
            recommendation=RecommendationValue.MERGE_SUPPORTING,
            created_ts="t",
        )


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        InvestigateResult(  # type: ignore[call-arg]
            run_id="r1", issue_text_hash="h1", bogus_field=1
        )


def test_session_trace_manifest_roundtrip() -> None:
    t = SessionTraceManifest(
        run_id="r1",
        issue_text_hash="h1",
        start_ts="t0",
        end_ts="t1",
        harness_condition_id="hcs:1",
    )
    rt = SessionTraceManifest.model_validate_json(t.model_dump_json())
    assert rt == t
