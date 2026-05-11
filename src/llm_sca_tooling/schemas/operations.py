"""Operational event payload models.

Each event family used by Phase 4A run records has a typed payload model.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from llm_sca_tooling.schemas.base import NonEmptyStr, StrictModel
from llm_sca_tooling.schemas.provenance import ArtifactRef, PolicyAction, Provenance

__all__ = [
    "BudgetKind",
    "ApprovalDecision",
    "MonitorAlertType",
    "GateType",
    "GateStatus",
    "ToolCallEvent",
    "ApprovalEvent",
    "BudgetEvent",
    "CompactionEvent",
    "MonitorAlert",
    "VerificationEvent",
    "MaintainabilityOracleResult",
    "PromptManifestRegressionResult",
]


class BudgetKind(str, Enum):
    tokens = "tokens"
    tool_calls = "tool_calls"
    retries = "retries"
    wall_clock_ms = "wall_clock_ms"
    artifact_bytes = "artifact_bytes"
    trace_bytes = "trace_bytes"
    context_items = "context_items"


class ApprovalDecision(str, Enum):
    approved = "approved"
    denied = "denied"
    expired = "expired"
    not_required = "not_required"


class MonitorAlertType(str, Enum):
    repeated_identical_tool_calls = "repeated_identical_tool_calls"
    repeated_failing_gate = "repeated_failing_gate"
    context_growth_without_new_evidence = "context_growth_without_new_evidence"
    denied_operation_storm = "denied_operation_storm"
    budget_exhaustion = "budget_exhaustion"
    stale_or_mixed_snapshot = "stale_or_mixed_snapshot"
    out_of_scope_write_attempt = "out_of_scope_write_attempt"
    missing_required_verification = "missing_required_verification"
    secret_or_redaction_failure = "secret_or_redaction_failure"  # noqa: S105
    cumulative_risk_placeholder = "cumulative_risk_placeholder"


class GateType(str, Enum):
    fmt = "format"  # 'format' is reserved by str; use .fmt in Python, "format" in JSON
    lint = "lint"
    typecheck = "typecheck"
    unit_test = "unit_test"
    integration_test = "integration_test"
    sast = "sast"
    secrets = "secrets"
    dependency_scan = "dependency_scan"
    contract = "contract"
    maintainability = "maintainability"
    manifest_regression = "manifest_regression"
    prompt_regression = "prompt_regression"
    custom = "custom"


class GateStatus(str, Enum):
    passed = "passed"
    failed = "failed"
    skipped = "skipped"
    unknown = "unknown"


class ToolCallEvent(StrictModel):
    tool_call_id: NonEmptyStr
    tool_name: NonEmptyStr
    arguments_hash: str | None = None
    argument_artifact_ref: ArtifactRef | None = None
    scope: str | None = None
    side_effect_class: str = "none"
    permission_mode: str = "read"
    network_required: bool = False
    policy_decision_id: str | None = None
    status: str = "unknown"
    result_ref: ArtifactRef | None = None
    retry_count: int = 0
    token_count: int | None = None
    wall_ms: int | None = None
    provenance: Provenance


class ApprovalEvent(StrictModel):
    approval_id: NonEmptyStr
    requested_action: str
    requested_by: str
    decision: ApprovalDecision
    decided_by: str
    reason: str | None = None
    scope: str | None = None
    ts: NonEmptyStr
    related_tool_call_id: str | None = None
    provenance: Provenance


class BudgetEvent(StrictModel):
    budget_event_id: NonEmptyStr
    budget_kind: BudgetKind
    limit: float
    used: float
    unit: str
    threshold: float | None = None
    action: PolicyAction = PolicyAction.not_applicable
    reason: str | None = None
    checkpoint_ref: str | None = None
    provenance: Provenance


class CompactionEvent(StrictModel):
    compaction_event_id: NonEmptyStr
    source_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    summary_artifact_ref: ArtifactRef | None = None
    removed_evidence_refs: list[str] = Field(default_factory=list)
    retained_evidence_refs: list[str] = Field(default_factory=list)
    reason: str | None = None
    loss_assessment: str | None = None
    forces_unknown: bool = False
    provenance: Provenance


class MonitorAlert(StrictModel):
    alert_id: NonEmptyStr
    alert_type: MonitorAlertType
    severity: str = "warning"
    run_id: NonEmptyStr
    event_ids: list[str] = Field(default_factory=list)
    description: str
    policy_action: PolicyAction = PolicyAction.not_applicable
    incident_id: str | None = None
    provenance: Provenance


class VerificationEvent(StrictModel):
    verification_id: NonEmptyStr
    run_id: NonEmptyStr
    gate_name: NonEmptyStr
    gate_type: GateType
    command_ref: str | None = None
    status: GateStatus = GateStatus.unknown
    started_ts: str | None = None
    ended_ts: str | None = None
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    summary: str | None = None
    skip_reason: str | None = None
    policy_action: PolicyAction = PolicyAction.not_applicable
    provenance: Provenance


class MaintainabilityOracleResult(StrictModel):
    oracle_result_id: NonEmptyStr
    run_id: NonEmptyStr
    oracle_name: NonEmptyStr
    status: GateStatus = GateStatus.unknown
    findings: list[str] = Field(default_factory=list)
    affected_refs: list[str] = Field(default_factory=list)
    policy_action: PolicyAction = PolicyAction.not_applicable
    provenance: Provenance


class RegressionCaseType(str, Enum):
    visible_behavior = "visible_behavior"
    hidden_policy = "hidden_policy"
    tool_order = "tool_order"
    semantic_mutation = "semantic_mutation"
    spec_evolution = "spec_evolution"


class PromptManifestRegressionResult(StrictModel):
    regression_result_id: NonEmptyStr
    run_id: NonEmptyStr
    target_ref: NonEmptyStr
    case_id: NonEmptyStr
    case_type: RegressionCaseType
    expected_behavior: str
    actual_behavior_ref: str | None = None
    status: GateStatus = GateStatus.unknown
    policy_action: PolicyAction = PolicyAction.not_applicable
    provenance: Provenance
