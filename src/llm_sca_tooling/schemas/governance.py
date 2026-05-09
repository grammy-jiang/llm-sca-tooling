"""Permission, policy, and governance contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from llm_sca_tooling.schemas.base import (
    SCHEMA_VERSION,
    StrictBaseModel,
    id_field,
)
from llm_sca_tooling.schemas.enums import (
    DriftClassification,
    PermissionMode,
    PolicyAction,
    RedactionStatus,
    SideEffectClass,
)
from llm_sca_tooling.schemas.provenance import ArtifactRef, Provenance, RepoRef


class ToolPermission(StrictBaseModel):
    tool_name: str = Field(min_length=1)
    required_mode: PermissionMode
    path_scope: str = Field(min_length=1)
    network_requirement: str = Field(min_length=1)
    side_effect_class: SideEffectClass
    approval_requirement: str = Field(min_length=1)
    allowed_stages: list[str] = Field(default_factory=list)
    deny_reason: str | None = None


class PolicyDecision(StrictBaseModel):
    policy_decision_id: str = id_field("Policy decision identifier.")
    policy_id: str = Field(min_length=1)
    run_id: str | None = None
    event_id: str | None = None
    tool_name: str | None = None
    requested_action: str = Field(min_length=1)
    decision: PolicyAction
    reasons: list[str] = Field(default_factory=list)
    required_approval: bool = False
    path_scope_result: str | None = None
    network_result: str | None = None
    side_effect_result: str | None = None
    stage_result: str | None = None
    provenance: Provenance


class ManifestPrecedenceRecord(StrictBaseModel):
    schema_family: Literal["governance"] = "governance"
    schema_version: str = SCHEMA_VERSION
    manifest_state_id: str = id_field("Manifest state identifier.")
    repo: RepoRef
    canonical_manifest_ref: ArtifactRef
    runtime_overlay_refs: list[ArtifactRef] = Field(default_factory=list)
    skill_refs: list[ArtifactRef] = Field(default_factory=list)
    effective_policy_hash: str = Field(min_length=1)
    precedence_order: list[str] = Field(default_factory=list)
    non_relaxation_result: str = Field(min_length=1)
    drift_findings: list[str] = Field(default_factory=list)
    provenance: Provenance


class HardConstraint(StrictBaseModel):
    constraint_id: str = id_field("Hard constraint identifier.")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    applies_to: list[str] = Field(default_factory=list)
    check_type: str = Field(min_length=1)
    policy_action: PolicyAction
    source_manifest_ref: str = Field(min_length=1)


class ManifestHash(StrictBaseModel):
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=1)


class RuntimeRef(StrictBaseModel):
    runtime_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str | None = None


class ModelBackendRef(StrictBaseModel):
    backend_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    version: str | None = None
    calibration_family: str | None = None


class ContextBudget(StrictBaseModel):
    max_tokens: int | None = Field(default=None, ge=0)
    max_tool_calls: int | None = Field(default=None, ge=0)
    max_wall_ms: int | None = Field(default=None, ge=0)
    max_artifact_bytes: int | None = Field(default=None, ge=0)
    policy_action_on_exhaustion: PolicyAction = PolicyAction.FORCE_UNKNOWN


class RetryPolicy(StrictBaseModel):
    max_retries: int = Field(ge=0)
    retryable_statuses: list[str] = Field(default_factory=list)
    policy_action_on_exhaustion: PolicyAction = PolicyAction.CHECKPOINT


class SandboxDescriptor(StrictBaseModel):
    kind: str = Field(min_length=1)
    image_ref: str | None = None
    writes_allowed: bool
    network_allowed: bool
    path_scope: str = Field(min_length=1)


class RedactionPolicy(StrictBaseModel):
    policy_id: str = Field(min_length=1)
    default_status: RedactionStatus
    rules_ref: str | None = None
    raw_prompt_retention: str = "artifact_ref_only"


class VerificationGate(StrictBaseModel):
    gate_name: str = Field(min_length=1)
    gate_type: str = Field(min_length=1)
    required: bool
    command_ref: str | None = None
    policy_action_on_failure: PolicyAction = PolicyAction.BLOCKED


class DriftFindingRef(StrictBaseModel):
    drift_id: str = Field(min_length=1)
    classification: DriftClassification
    blocks_release: bool


class WaiverRef(StrictBaseModel):
    waiver_id: str = Field(min_length=1)
    reviewed_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    expires_ts: str | None = None


class GovernanceDocument(StrictBaseModel):
    schema_family: Literal["governance"] = "governance"
    schema_version: str = SCHEMA_VERSION
    governance_id: str = id_field("Governance document identifier.")
    tool_permissions: list[ToolPermission] = Field(default_factory=list)
    policy_decisions: list[PolicyDecision] = Field(default_factory=list)
    manifest_state: ManifestPrecedenceRecord | None = None
    hard_constraints: list[HardConstraint] = Field(default_factory=list)
    provenance: Provenance


def baseline_hard_constraints(
    source_manifest_ref: str = "AGENTS.md",
) -> list[HardConstraint]:
    constraints = [
        (
            "HC1",
            "No plaintext secrets",
            "No plaintext secrets in repo, prompts, logs, or commits.",
        ),
        (
            "HC2",
            "Path allowlist",
            "No writes outside the repository or path allowlist.",
        ),
        (
            "HC3",
            "Destructive approval",
            "Destructive commands require explicit human approval.",
        ),
        (
            "HC4",
            "No irreversible migrations",
            "Irreversible migrations may be authored but not executed by agents.",
        ),
        ("HC5", "Deny network by default", "Network egress is denied by default."),
        (
            "HC6",
            "No red-class data",
            "Red-class data never enters prompts, tool arguments, or logs.",
        ),
    ]
    return [
        HardConstraint(
            constraint_id=constraint_id,
            name=name,
            description=description,
            severity="blocking",
            applies_to=["agent", "workflow", "release"],
            check_type="policy",
            policy_action=PolicyAction.BLOCKED,
            source_manifest_ref=source_manifest_ref,
        )
        for constraint_id, name, description in constraints
    ]
