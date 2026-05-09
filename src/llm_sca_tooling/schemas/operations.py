"""Operational event payload and verification models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import StrictBaseModel, id_field, ordered_ts
from llm_sca_tooling.schemas.enums import PolicyAction, RedactionStatus, Severity, Status
from llm_sca_tooling.schemas.governance import PolicyDecision
from llm_sca_tooling.schemas.provenance import ArtifactRef, Provenance


class ToolCallEvent(StrictBaseModel):
    tool_call_id: str = id_field("Tool call identifier.")
    tool_name: str = Field(min_length=1)
    arguments_hash: str | None = None
    argument_artifact_ref: ArtifactRef | None = None
    scope: str = Field(min_length=1)
    side_effect_class: str = Field(min_length=1)
    permission_mode: str = Field(min_length=1)
    network_required: bool
    policy_decision_id: str | None = None
    status: Status
    result_ref: ArtifactRef | None = None
    retry_count: int = Field(ge=0)
    token_count: int | None = Field(default=None, ge=0)
    wall_ms: int | None = Field(default=None, ge=0)
    provenance: Provenance


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    NOT_REQUIRED = "not_required"


class ApprovalEvent(StrictBaseModel):
    approval_id: str = id_field("Approval identifier.")
    requested_action: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    decision: ApprovalDecision
    decided_by: str | None = None
    reason: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    ts: str = Field(min_length=1)
    related_tool_call_id: str | None = None
    provenance: Provenance


class BudgetKind(StrEnum):
    TOKENS = "tokens"
    TOOL_CALLS = "tool_calls"
    RETRIES = "retries"
    WALL_CLOCK_MS = "wall_clock_ms"
    ARTIFACT_BYTES = "artifact_bytes"
    TRACE_BYTES = "trace_bytes"
    CONTEXT_ITEMS = "context_items"


class BudgetEvent(StrictBaseModel):
    budget_event_id: str = id_field("Budget event identifier.")
    budget_kind: BudgetKind
    limit: float = Field(ge=0)
    used: float = Field(ge=0)
    unit: str = Field(min_length=1)
    threshold: float = Field(ge=0)
    action: PolicyAction
    reason: str = Field(min_length=1)
    checkpoint_ref: str | None = None
    provenance: Provenance


class CompactionEvent(StrictBaseModel):
    compaction_event_id: str = id_field("Compaction event identifier.")
    source_artifact_refs: list[ArtifactRef]
    summary_artifact_ref: ArtifactRef
    removed_evidence_refs: list[str] = Field(default_factory=list)
    retained_evidence_refs: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    loss_assessment: str = Field(min_length=1)
    forces_unknown: bool
    provenance: Provenance

    @model_validator(mode="after")
    def validate_source_refs(self) -> "CompactionEvent":
        if not self.source_artifact_refs:
            raise ValueError("compaction must link to source artefacts")
        return self


class MonitorAlertType(StrEnum):
    REPEATED_IDENTICAL_TOOL_CALLS = "repeated_identical_tool_calls"
    REPEATED_FAILING_GATE = "repeated_failing_gate"
    CONTEXT_GROWTH_WITHOUT_NEW_EVIDENCE = "context_growth_without_new_evidence"
    DENIED_OPERATION_STORM = "denied_operation_storm"
    BUDGET_EXHAUSTION = "budget_exhaustion"
    STALE_OR_MIXED_SNAPSHOT = "stale_or_mixed_snapshot"
    OUT_OF_SCOPE_WRITE_ATTEMPT = "out_of_scope_write_attempt"
    MISSING_REQUIRED_VERIFICATION = "missing_required_verification"
    SECRET_OR_REDACTION_FAILURE = "secret_or_redaction_failure"
    CUMULATIVE_RISK_PLACEHOLDER = "cumulative_risk_placeholder"


class MonitorAlert(StrictBaseModel):
    alert_id: str = id_field("Monitor alert identifier.")
    alert_type: MonitorAlertType
    severity: Severity
    run_id: str = Field(min_length=1)
    event_ids: list[str] = Field(default_factory=list)
    description: str = Field(min_length=1)
    policy_action: PolicyAction
    incident_id: str | None = None
    provenance: Provenance


class GateType(StrEnum):
    FORMAT = "format"
    LINT = "lint"
    TYPECHECK = "typecheck"
    UNIT_TEST = "unit_test"
    INTEGRATION_TEST = "integration_test"
    SAST = "sast"
    SECRETS = "secrets"
    DEPENDENCY_SCAN = "dependency_scan"
    CONTRACT = "contract"
    MAINTAINABILITY = "maintainability"
    MANIFEST_REGRESSION = "manifest_regression"
    PROMPT_REGRESSION = "prompt_regression"
    CUSTOM = "custom"


class VerificationEvent(StrictBaseModel):
    verification_id: str = id_field("Verification event identifier.")
    run_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    gate_type: GateType
    command_ref: str | None = None
    status: Status
    started_ts: str = Field(min_length=1)
    ended_ts: str | None = None
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    policy_action: PolicyAction
    provenance: Provenance

    @model_validator(mode="after")
    def validate_verification(self) -> "VerificationEvent":
        if not ordered_ts(self.started_ts, self.ended_ts):
            raise ValueError("verification ended_ts cannot be earlier than started_ts")
        if self.status == Status.SKIPPED and not self.summary:
            raise ValueError("skipped gates require reasons")
        return self


class MaintainabilityOracleResult(StrictBaseModel):
    oracle_result_id: str = id_field("Maintainability oracle result identifier.")
    run_id: str = Field(min_length=1)
    oracle_name: str = Field(min_length=1)
    status: Status
    findings: list[str] = Field(default_factory=list)
    affected_refs: list[str] = Field(default_factory=list)
    policy_action: PolicyAction
    provenance: Provenance


class RegressionCaseType(StrEnum):
    VISIBLE_BEHAVIOR = "visible_behavior"
    HIDDEN_POLICY = "hidden_policy"
    TOOL_ORDER = "tool_order"
    SEMANTIC_MUTATION = "semantic_mutation"
    SPEC_EVOLUTION = "spec_evolution"


class PromptManifestRegressionResult(StrictBaseModel):
    regression_result_id: str = id_field("Regression result identifier.")
    run_id: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    case_type: RegressionCaseType
    expected_behavior: str = Field(min_length=1)
    actual_behavior_ref: str = Field(min_length=1)
    status: Status
    policy_action: PolicyAction
    provenance: Provenance
