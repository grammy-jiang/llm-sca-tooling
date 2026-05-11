"""Permission, policy, and governance models."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from llm_sca_tooling.schemas.base import NonEmptyStr, StrictModel
from llm_sca_tooling.schemas.provenance import PolicyAction, Provenance

__all__ = [
    "PermissionMode",
    "SideEffectClass",
    "ToolPermission",
    "PolicyDecisionSchema",
    "DriftClassification",
    "ManifestPrecedenceRecord",
    "HardConstraint",
]


class PermissionMode(str, Enum):
    read = "read"
    search = "search"
    edit = "edit"
    execute = "execute"
    review = "review"
    commit = "commit"


class SideEffectClass(str, Enum):
    none = "none"
    read_only = "read_only"
    writes_repo = "writes_repo"
    writes_outside_repo = "writes_outside_repo"
    executes_code = "executes_code"
    network = "network"
    destructive = "destructive"
    release = "release"


class ToolPermission(StrictModel):
    tool_name: NonEmptyStr
    required_mode: PermissionMode
    path_scope: str | None = None
    network_requirement: bool = False
    side_effect_class: SideEffectClass = SideEffectClass.none
    approval_requirement: bool = False
    allowed_stages: list[str] = Field(default_factory=list)
    deny_reason: str | None = None


class PolicyDecisionSchema(StrictModel):
    """Schema-layer policy decision record (distinct from governance.PolicyDecision)."""

    policy_decision_id: NonEmptyStr
    policy_id: NonEmptyStr
    run_id: str | None = None
    event_id: str | None = None
    tool_name: NonEmptyStr
    requested_action: str
    decision: PolicyAction
    reasons: list[str] = Field(default_factory=list)
    required_approval: bool = False
    path_scope_result: str | None = None
    network_result: str | None = None
    side_effect_result: str | None = None
    stage_result: str | None = None
    provenance: Provenance


class DriftClassification(str, Enum):
    missing = "missing"
    stale = "stale"
    relaxed = "relaxed"
    out_of_stage = "out-of-stage"
    clean = "clean"


class ManifestPrecedenceRecord(StrictModel):
    manifest_state_id: NonEmptyStr
    canonical_manifest_ref: NonEmptyStr
    runtime_overlay_refs: list[str] = Field(default_factory=list)
    skill_refs: list[str] = Field(default_factory=list)
    effective_policy_hash: str | None = None
    precedence_order: list[str] = Field(default_factory=list)
    non_relaxation_result: str = "unknown"
    drift_findings: list[str] = Field(default_factory=list)
    provenance: Provenance


class HardConstraint(StrictModel):
    constraint_id: NonEmptyStr
    name: NonEmptyStr
    description: str
    severity: str = "critical"
    applies_to: list[str] = Field(default_factory=list)
    check_type: str = "static"
    policy_action: PolicyAction = PolicyAction.deny
    source_manifest_ref: str | None = None


# Built-in HC1–HC6 constraints
HC1 = HardConstraint(
    constraint_id="HC1",
    name="No plaintext secrets",
    description="No secrets in repo files, prompts, logs, or commits.",
    check_type="detect-secrets",
)
HC2 = HardConstraint(
    constraint_id="HC2",
    name="No writes outside path allowlist",
    description="No agent-authored writes outside the repo/path allowlist.",
    check_type="path-check",
)
HC3 = HardConstraint(
    constraint_id="HC3",
    name="Explicit approval for destructive commands",
    description="Destructive commands require explicit human approval.",
    check_type="approval-gate",
)
HC4 = HardConstraint(
    constraint_id="HC4",
    name="No agent-executed irreversible migrations",
    description="Migrations must be authored but never autonomously executed.",
    check_type="approval-gate",
)
HC5 = HardConstraint(
    constraint_id="HC5",
    name="Deny-by-default network egress",
    description="No network calls outside the explicitly allowed list.",
    check_type="network-policy",
)
HC6 = HardConstraint(
    constraint_id="HC6",
    name="No red-class data in prompts or logs",
    description="No PII, credentials, or red-class data in prompts, args, or logs.",
    check_type="redaction-check",
)

HARD_CONSTRAINTS: list[HardConstraint] = [HC1, HC2, HC3, HC4, HC5, HC6]
