"""Tests for run record and event models."""

from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.base import canonical_dumps, canonical_loads
from llm_sca_tooling.schemas.provenance import PolicyAction, RedactionStatus
from llm_sca_tooling.schemas.run_records import (
    ActorType,
    RunEvent,
    RunEventType,
    RunRecord,
    RunStatus,
    RunWorkflow,
    validate_event_sequence,
)

NOW = "2026-05-09T12:00:00Z"


def _make_run(
    status: RunStatus = RunStatus.running, end_ts: str | None = None
) -> RunRecord:
    return RunRecord(
        run_id="run:001",
        workflow=RunWorkflow.bug_resolve,
        start_ts=NOW,
        end_ts=end_ts,
        status=status,
        created_ts=NOW,
    )


def _make_event(seq: int, run_id: str = "run:001") -> RunEvent:
    return RunEvent(
        event_id=f"evt:{seq}",
        run_id=run_id,
        seq=seq,
        ts=NOW,
        type=RunEventType.tool_call_started,
        actor=ActorType.agent,
        stage="execution",
        redaction_status=RedactionStatus.not_required,
    )


def test_run_record_round_trip() -> None:
    run = _make_run()
    dumped = canonical_dumps(run)
    loaded = canonical_loads(dumped, RunRecord)
    assert loaded.run_id == run.run_id
    assert loaded.workflow == RunWorkflow.bug_resolve


def test_completed_run_without_end_ts_rejected() -> None:
    with pytest.raises(ValueError, match="end_ts"):
        _make_run(status=RunStatus.completed, end_ts=None)


def test_completed_run_with_end_ts_valid() -> None:
    run = _make_run(status=RunStatus.completed, end_ts=NOW)
    assert run.status == RunStatus.completed


def test_event_sequence_valid() -> None:
    events = [_make_event(1), _make_event(2), _make_event(3)]
    errors = validate_event_sequence(events, "run:001")
    assert errors == []


def test_event_sequence_duplicate_rejected() -> None:
    events = [_make_event(1), _make_event(1)]
    errors = validate_event_sequence(events, "run:001")
    assert any("duplicate" in e for e in errors)


def test_event_sequence_non_monotonic_rejected() -> None:
    events = [_make_event(2), _make_event(1)]
    errors = validate_event_sequence(events, "run:001")
    assert any("non-monotonic" in e for e in errors)


def test_event_run_id_mismatch_detected() -> None:
    events = [_make_event(1, run_id="run:OTHER")]
    errors = validate_event_sequence(events, "run:001")
    assert any("run_id" in e for e in errors)


def test_run_event_missing_redaction_status_rejected() -> None:
    with pytest.raises(Exception):
        RunEvent(
            event_id="e1",
            run_id="run:1",
            seq=1,
            ts=NOW,
            type=RunEventType.session_start,
            actor=ActorType.system,
            stage="start",
        )


def test_policy_action_representable_in_event() -> None:
    e = _make_event(1)
    e2 = e.model_copy(update={"policy_action": PolicyAction.deny})
    assert e2.policy_action == PolicyAction.deny
