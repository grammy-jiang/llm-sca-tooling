"""Patch and risk-finding contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, id_field
from llm_sca_tooling.schemas.enums import PolicyAction
from llm_sca_tooling.schemas.provenance import (
    ArtifactRef,
    Provenance,
    RepoRef,
    SnapshotRef,
)


class RiskClass(StrEnum):
    SAFE = "safe"
    CORRECT_BUT_OVERFIT = "correct-but-overfit"
    VULNERABLE = "vulnerable"
    VULNERABILITY_INTRODUCING = "vulnerability-introducing"
    RISKY = "risky"
    UNKNOWN = "unknown"


class PatchRecord(StrictBaseModel):
    patch_id: str = id_field("Patch identifier.")
    diff_id: str = Field(min_length=1)
    repo: RepoRef
    base_snapshot: SnapshotRef
    target_snapshot: SnapshotRef
    changed_files: list[str] = Field(default_factory=list)
    changed_symbols: list[str] = Field(default_factory=list)
    diff_artifact: ArtifactRef | None = None
    generated_by_run_id: str | None = None
    provenance: Provenance
    attributes: JsonObject = Field(default_factory=dict)


class RiskFinding(StrictBaseModel):
    finding_id: str = id_field("Risk finding identifier.")
    diff_id: str = Field(min_length=1)
    changed_symbols: list[str] = Field(default_factory=list)
    sarif_delta_id: str | None = None
    test_delta_id: str | None = None
    risk_class: RiskClass
    calibrated_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    ece_bucket: str | None = None
    policy_action: PolicyAction
    evidence_bundle_id: str = Field(min_length=1)
    provenance: Provenance
    uncertainty: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_risk(self) -> RiskFinding:
        if self.risk_class == RiskClass.SAFE and not (
            self.sarif_delta_id or self.test_delta_id
        ):
            raise ValueError("safe risk findings require deterministic gate support")
        if self.risk_class != RiskClass.UNKNOWN and self.calibrated_probability is None:
            raise ValueError("non-unknown risk findings require calibrated_probability")
        return self
