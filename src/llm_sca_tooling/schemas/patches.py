"""Patch and risk finding models."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonValue, NonEmptyStr, StrictModel
from llm_sca_tooling.schemas.provenance import (
    ArtifactRef,
    PolicyAction,
    Provenance,
    RepoRef,
    SnapshotRef,
)

__all__ = ["RiskClass", "PatchRecord", "RiskFinding"]


class RiskClass(str, Enum):
    safe = "safe"
    correct_but_overfit = "correct-but-overfit"
    vulnerable = "vulnerable"
    vulnerability_introducing = "vulnerability-introducing"
    risky = "risky"
    unknown = "unknown"


class PatchRecord(StrictModel):
    patch_id: NonEmptyStr
    diff_id: NonEmptyStr
    repo: RepoRef
    base_snapshot: SnapshotRef
    target_snapshot: SnapshotRef | None = None
    changed_files: list[str] = Field(default_factory=list)
    changed_symbols: list[str] = Field(default_factory=list)
    diff_artifact: ArtifactRef | None = None
    generated_by_run_id: str | None = None
    provenance: Provenance
    attributes: dict[str, JsonValue] = Field(default_factory=dict)


class RiskFinding(StrictModel):
    finding_id: NonEmptyStr
    diff_id: NonEmptyStr
    changed_symbols: list[str] = Field(default_factory=list)
    sarif_delta_id: str | None = None
    test_delta_id: str | None = None
    risk_class: RiskClass = RiskClass.unknown
    calibrated_probability: float | None = None
    ece_bucket: str | None = None
    policy_action: PolicyAction = PolicyAction.not_applicable
    evidence_bundle_id: str | None = None
    provenance: Provenance
    uncertainty: str | None = None
