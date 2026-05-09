"""Run record, run event, and session trace contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import JsonObject, SCHEMA_VERSION, StrictBaseModel, id_field, ordered_ts
from llm_sca_tooling.schemas.enums import PolicyAction, RedactionStatus, Status
from llm_sca_tooling.schemas.governance import ContextBudget, ModelBackendRef, RedactionPolicy
from llm_sca_tooling.schemas.provenance import ArtifactRef, RepoRef


class Workflow(StrEnum):
    IMPLEMENTATION_CHECK = "implementation-check"
    BUG_RESOLVE = "bug-resolve"
    PATCH_REVIEW = "patch-review"
    OPERATIONAL_REVIEW = "operational-review"
    READINESS_AUDIT = "readiness-audit"
    EVAL = "eval"
    GRAPH_BUILD = "graph-build"
    GRAPH_UPDATE = "graph-update"
    OTHER = "other"


class RunEventType(StrEnum):
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    HARNESS_CONDITION_RECORDED = "harness_condition_recorded"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    CONTEXT_LOADED = "context_loaded"
    CONTEXT_COMPACTED = "context_compacted"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_CALL_FAILED = "tool_call_failed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    POLICY_DECISION = "policy_decision"
    BUDGET_WARNING = "budget_warning"
    BUDGET_HARD_STOP = "budget_hard_stop"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"
    MONITOR_ALERT = "monitor_alert"
    INCIDENT_OPENED = "incident_opened"
    INCIDENT_UPDATED = "incident_updated"
    INCIDENT_CLOSED = "incident_closed"
    PROMOTION_CANDIDATE_CREATED = "promotion_candidate_created"
    REVIEWER_DECISION = "reviewer_decision"
    FINAL_VERDICT_RECORDED = "final_verdict_recorded"


class Actor(StrEnum):
    USER = "user"
    AGENT = "agent"
    TOOL = "tool"
    POLICY = "policy"
    SYSTEM = "system"
    REVIEWER = "reviewer"
    MONITOR = "monitor"


class RunEvent(StrictBaseModel):
    schema_family: Literal["run-record"] = "run-record"
    schema_version: str = SCHEMA_VERSION
    event_id: str = id_field("Run event identifier.")
    run_id: str = Field(min_length=1)
    seq: int = Field(gt=0)
    ts: str = Field(min_length=1)
    type: RunEventType
    actor: Actor
    stage: str = Field(min_length=1)
    input_ref: str | None = None
    output_ref: str | None = None
    policy_action: PolicyAction | None = None
    token_count: int | None = Field(default=None, ge=0)
    wall_ms: int | None = Field(default=None, ge=0)
    artefact_ids: list[str] = Field(default_factory=list)
    redaction_status: RedactionStatus
    payload: JsonObject = Field(default_factory=dict)


class RunRecord(StrictBaseModel):
    schema_family: Literal["run-record"] = "run-record"
    schema_version: str = SCHEMA_VERSION
    run_id: str = id_field("Run identifier.")
    workflow: Workflow
    user_intent_hash: str = Field(min_length=1)
    repos: list[RepoRef]
    start_ts: str = Field(min_length=1)
    end_ts: str | None = None
    status: Status
    model_backend: ModelBackendRef | None = None
    toolset_hash: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    permission_profile: str = Field(min_length=1)
    context_budget: ContextBudget
    run_event_count: int = Field(ge=0)
    harness_condition_id: str = Field(min_length=1)
    final_verdict_id: str | None = None
    incident_ids: list[str] = Field(default_factory=list)
    redaction_policy: RedactionPolicy
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    created_ts: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_run(self) -> "RunRecord":
        if self.status == Status.COMPLETED and not self.end_ts:
            raise ValueError("completed runs require end_ts")
        if not ordered_ts(self.start_ts, self.end_ts):
            raise ValueError("end_ts cannot be earlier than start_ts")
        if not self.repos:
            raise ValueError("run records require at least one repo")
        return self


class SessionTrace(StrictBaseModel):
    trace_id: str = id_field("Session trace identifier.")
    run_id: str | None = None
    session_start_ts: str = Field(min_length=1)
    session_end_ts: str | None = None
    events: list[RunEvent] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    redaction_policy: RedactionPolicy


def validate_run_events(record: RunRecord, events: list[RunEvent], require_contiguous: bool = True) -> None:
    if record.run_event_count != len(events):
        raise ValueError("run_event_count must match event list length")
    seen: set[int] = set()
    for event in events:
        if event.run_id != record.run_id:
            raise ValueError("run event run_id must match owning run")
        if event.seq in seen:
            raise ValueError("run events must have unique sequence numbers")
        seen.add(event.seq)
    ordered = sorted(seen)
    if require_contiguous and ordered != list(range(1, len(events) + 1)):
        raise ValueError("run event sequence must be contiguous from 1")
