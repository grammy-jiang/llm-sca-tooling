"""Run record and session trace schema models.

These are the typed schema-layer models.  The Phase 0 file-based writer
(``operations.run_records``) will be updated to emit conformant payloads
in Phase 4A.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import (
    SCHEMA_VERSION,
    JsonValue,
    NonEmptyStr,
    StrictModel,
)
from llm_sca_tooling.schemas.provenance import (
    ArtifactRef,
    PolicyAction,
    RedactionStatus,
    RepoRef,
)

__all__ = [
    "RunStatus",
    "RunWorkflow",
    "RunEventType",
    "ActorType",
    "RunRecord",
    "RunEvent",
    "SessionTrace",
    "validate_event_sequence",
]


class RunStatus(str, Enum):
    created = "created"
    running = "running"
    blocked = "blocked"
    failed = "failed"
    completed = "completed"
    cancelled = "cancelled"
    unknown = "unknown"
    budget_exhausted = "budget-exhausted"


class RunWorkflow(str, Enum):
    implementation_check = "implementation-check"
    bug_resolve = "bug-resolve"
    patch_review = "patch-review"
    operational_review = "operational-review"
    readiness_audit = "readiness-audit"
    eval = "eval"
    graph_build = "graph-build"
    graph_update = "graph-update"
    other = "other"


class RunEventType(str, Enum):
    session_start = "session_start"
    session_end = "session_end"
    harness_condition_recorded = "harness_condition_recorded"
    stage_started = "stage_started"
    stage_completed = "stage_completed"
    context_loaded = "context_loaded"
    context_compacted = "context_compacted"
    tool_call_started = "tool_call_started"
    tool_call_completed = "tool_call_completed"
    tool_call_failed = "tool_call_failed"
    approval_requested = "approval_requested"
    approval_granted = "approval_granted"
    approval_denied = "approval_denied"
    policy_decision = "policy_decision"
    budget_warning = "budget_warning"
    budget_hard_stop = "budget_hard_stop"
    verification_started = "verification_started"
    verification_completed = "verification_completed"
    monitor_alert = "monitor_alert"
    incident_opened = "incident_opened"
    incident_updated = "incident_updated"
    incident_closed = "incident_closed"
    promotion_candidate_created = "promotion_candidate_created"
    reviewer_decision = "reviewer_decision"
    final_verdict_recorded = "final_verdict_recorded"


class ActorType(str, Enum):
    user = "user"
    agent = "agent"
    tool = "tool"
    policy = "policy"
    system = "system"
    reviewer = "reviewer"
    monitor = "monitor"


class ContextBudget(StrictModel):
    max_tokens: int | None = None
    max_tool_calls: int | None = None
    max_retries: int | None = None
    max_wall_seconds: int | None = None
    compaction_threshold_pct: float = 0.70


class RedactionPolicy(StrictModel):
    policy_id: NonEmptyStr = "default"
    redact_prompts: bool = True
    redact_source_files: bool = False
    redact_command_output: bool = False
    hash_paths: bool = True


class RunEvent(StrictModel):
    schema_family: str = "run-record"
    schema_version: str = SCHEMA_VERSION
    event_id: NonEmptyStr
    run_id: NonEmptyStr
    seq: Annotated[int, Field(ge=1)]
    ts: NonEmptyStr
    type: RunEventType
    actor: ActorType
    stage: str
    input_ref: str | None = None
    output_ref: str | None = None
    policy_action: PolicyAction | None = None
    token_count: int | None = None
    wall_ms: int | None = None
    artefact_ids: list[str] = Field(default_factory=list)
    redaction_status: RedactionStatus
    payload: dict[str, JsonValue] = Field(default_factory=dict)


class RunRecord(StrictModel):
    schema_family: str = "run-record"
    schema_version: str = SCHEMA_VERSION
    run_id: NonEmptyStr
    workflow: RunWorkflow = RunWorkflow.other
    user_intent_hash: str = ""
    repos: list[RepoRef] = Field(default_factory=list)
    start_ts: NonEmptyStr
    end_ts: str | None = None
    status: RunStatus = RunStatus.created
    model_backend: str | None = None
    toolset_hash: str = "unknown"
    policy_id: str = "unknown"
    permission_profile: str = "read-only"
    context_budget: ContextBudget = ContextBudget()
    run_event_count: int = 0
    harness_condition_id: str | None = None
    final_verdict_id: str | None = None
    incident_ids: list[str] = Field(default_factory=list)
    redaction_policy: RedactionPolicy = RedactionPolicy()
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    created_ts: NonEmptyStr

    @model_validator(mode="after")
    def _completed_needs_end_ts(self) -> RunRecord:
        if self.status == RunStatus.completed and self.end_ts is None:
            raise ValueError("completed run must have end_ts")
        return self


class SessionTrace(StrictModel):
    trace_id: NonEmptyStr
    run_id: str | None = None
    session_start_ts: NonEmptyStr
    session_end_ts: str | None = None
    events: list[RunEvent] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    redaction_policy: RedactionPolicy = RedactionPolicy()


def validate_event_sequence(events: list[RunEvent], run_id: str) -> list[str]:
    """Validate event sequence monotonicity and run_id consistency.

    Returns a list of violation messages (empty means valid).
    """
    errors: list[str] = []
    seen_seqs: set[int] = set()
    prev_seq = 0
    for event in events:
        if event.run_id != run_id:
            errors.append(
                f"event {event.event_id!r} run_id {event.run_id!r} != {run_id!r}"
            )
        if event.seq in seen_seqs:
            errors.append(f"duplicate seq {event.seq} in event {event.event_id!r}")
        if event.seq <= prev_seq:
            errors.append(
                f"non-monotonic seq: {event.seq} after {prev_seq} "
                f"(event {event.event_id!r})"
            )
        seen_seqs.add(event.seq)
        prev_seq = event.seq
    return errors
