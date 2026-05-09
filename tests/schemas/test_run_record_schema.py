from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.schemas.enums import PolicyAction, RedactionStatus, Status
from llm_sca_tooling.schemas.governance import ContextBudget, RedactionPolicy
from llm_sca_tooling.schemas.run_records import Actor, RunEvent, RunEventType, RunRecord, Workflow, validate_run_events

TS = "2026-05-09T00:00:00Z"


def record(repo) -> RunRecord:
    return RunRecord(
        run_id="run:demo",
        workflow=Workflow.IMPLEMENTATION_CHECK,
        user_intent_hash="hash:intent",
        repos=[repo],
        start_ts=TS,
        end_ts=TS,
        status=Status.COMPLETED,
        toolset_hash="hash:tools",
        policy_id="policy:default",
        permission_profile="default",
        context_budget=ContextBudget(max_tokens=1000),
        run_event_count=2,
        harness_condition_id="harness:demo",
        redaction_policy=RedactionPolicy(policy_id="redaction:default", default_status=RedactionStatus.REDACTED),
        created_ts=TS,
    )


def event(seq: int, run_id: str = "run:demo") -> RunEvent:
    return RunEvent(
        event_id=f"event:{run_id}:{seq}",
        run_id=run_id,
        seq=seq,
        ts=TS,
        type=RunEventType.POLICY_DECISION,
        actor=Actor.POLICY,
        stage="policy",
        policy_action=PolicyAction.DENY,
        artefact_ids=[],
        redaction_status=RedactionStatus.NOT_REQUIRED,
        payload={"reason": "denied action is recordable"},
    )


def test_run_record_round_trips(repo) -> None:
    assert RunRecord.model_validate_json(record(repo).model_dump_json()).run_id == "run:demo"


def test_sequence_validation_passes(repo) -> None:
    validate_run_events(record(repo), [event(1), event(2)])


def test_duplicate_sequence_fails(repo) -> None:
    with pytest.raises(ValueError):
        validate_run_events(record(repo), [event(1), event(1)])


def test_mismatched_run_id_fails(repo) -> None:
    with pytest.raises(ValueError):
        validate_run_events(record(repo), [event(1), event(2, "run:other")])


def test_missing_redaction_status_fails() -> None:
    with pytest.raises(ValidationError):
        RunEvent(event_id="event:1", run_id="run:1", seq=1, ts=TS, type=RunEventType.SESSION_START, actor=Actor.SYSTEM, stage="start")


def test_completed_run_requires_end_ts(repo) -> None:
    data = record(repo).model_dump(mode="python")
    data["end_ts"] = None
    with pytest.raises(ValidationError):
        RunRecord.model_validate(data)


def test_budget_hard_stop_can_be_represented() -> None:
    hard_stop = event(1)
    hard_stop = hard_stop.model_copy(update={"type": RunEventType.BUDGET_HARD_STOP, "policy_action": PolicyAction.FORCE_UNKNOWN})
    assert hard_stop.policy_action == PolicyAction.FORCE_UNKNOWN
