from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.enums import HarnessStage, PolicyAction, Severity, Status
from llm_sca_tooling.schemas.incidents import (
    Incident,
    IncidentStatus,
    PromotionCandidate,
    PromotionReviewState,
    PromotionTargetType,
    TimelineEntry,
)
from llm_sca_tooling.schemas.readiness import (
    AIReadinessReport,
    AxisScore,
    NoRegressionResult,
    ReadinessAxis,
    ThresholdResult,
)
from llm_sca_tooling.schemas.run_records import RunEventType, Workflow
from llm_sca_tooling.storage.errors import RunEventSequenceError
from llm_sca_tooling.storage.operations import OperationalRecord
from tests.storage.conftest import harness_condition, run_event, run_record

TS = "2026-05-09T00:00:00Z"


def test_run_event_append_close_and_queries(workspace, repo_ref, provenance) -> None:
    workspace.operations.create_run(run_record(repo_ref))
    workspace.operations.append_run_event("run:demo", run_event(1))
    with pytest.raises(RunEventSequenceError):
        workspace.operations.append_run_event("run:demo", run_event(1))
    assert (
        workspace.operations.get_run(
            "run:demo", include_events=True
        ).run.run_event_count
        == 1
    )
    closed = workspace.operations.close_run("run:demo", Status.COMPLETED, end_ts=TS)
    assert closed.status == Status.COMPLETED
    assert workspace.operations.query_runs(repo_id=repo_ref.repo_id)
    assert workspace.operations.query_runs(workflow=Workflow.IMPLEMENTATION_CHECK)
    assert workspace.operations.query_runs(status=Status.COMPLETED)
    assert workspace.operations.list_run_events(
        "run:demo", type=RunEventType.POLICY_DECISION
    )


def test_harness_condition_and_operational_record(
    workspace, repo_ref, provenance
) -> None:
    workspace.operations.create_run(run_record(repo_ref))
    condition = workspace.operations.record_harness_condition(
        harness_condition(provenance)
    )
    assert (
        workspace.operations.get_harness_condition(
            condition.harness_condition_id
        ).run_id
        == "run:demo"
    )
    record = OperationalRecord(
        record_id="op:policy",
        repo_id=repo_ref.repo_id,
        run_id="run:demo",
        kind="policy_decision",
        status="recorded",
        policy_action=PolicyAction.DENY,
        payload={"decision": "deny"},
    )
    workspace.operations.record_operational_record(record)
    assert (
        workspace.operations.query_operational_records(
            repo_id=repo_ref.repo_id, kind="policy_decision"
        )[0].policy_action
        == PolicyAction.DENY
    )


def test_incident_promotion_and_readiness_links(
    workspace, repo_ref, provenance
) -> None:
    workspace.operations.create_run(run_record(repo_ref))
    workspace.operations.append_run_event("run:demo", run_event(1))
    incident = Incident(
        incident_id="incident:1",
        severity=Severity.HIGH,
        status=IncidentStatus.OPEN,
        title="Loop",
        impact="lost time",
        timeline=[TimelineEntry(ts=TS, description="opened")],
        source_run_ids=["run:demo"],
        source_event_ids=["event:run:demo:1"],
        provenance=provenance,
    )
    workspace.operations.record_incident(incident, primary_repo_id=repo_ref.repo_id)
    assert (
        workspace.operations.query_runs(incident_id=incident.incident_id)[0].run_id
        == "run:demo"
    )
    candidate = PromotionCandidate(
        promotion_id="promotion:1",
        source_run_id="run:demo",
        source_event_ids=["event:run:demo:1"],
        target_type=PromotionTargetType.DETECTOR,
        target_ref="detector:loop",
        lesson_summary="detect loops",
        review_state=PromotionReviewState.REVIEWED,
        owner="team",
        review_due_ts=TS,
        rollback_path="remove detector",
        provenance=provenance,
    )
    workspace.operations.record_promotion_candidate(candidate)
    assert (
        workspace.operations.query_promotion_candidates(source_run_id="run:demo")[
            0
        ].promotion_id
        == "promotion:1"
    )
    report = AIReadinessReport(
        readiness_report_id="ready:1",
        repo=repo_ref,
        stage=HarnessStage.S1,
        total_score=5,
        axis_scores=[AxisScore(axis=axis, score=1) for axis in ReadinessAxis],
        threshold_result=ThresholdResult(
            target_stage=HarnessStage.S1, passed=True, reason="ok"
        ),
        no_regression_result=NoRegressionResult(passed=True, reason="ok"),
        provenance=provenance,
    )
    workspace.operations.record_readiness_report(report)
    assert (
        workspace.operations.query_readiness_reports(repo_ref.repo_id)[0].total_score
        == 5
    )
