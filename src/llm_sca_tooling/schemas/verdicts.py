"""Verdict contracts and evidence-aware validation."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import SCHEMA_VERSION, StrictBaseModel, id_field
from llm_sca_tooling.schemas.enums import EvidenceStrength, PolicyAction, VerdictValue
from llm_sca_tooling.schemas.evidence import EvidenceBundle
from llm_sca_tooling.schemas.provenance import Provenance

POSITIVE_VERDICTS = {
    VerdictValue.SATISFIED,
    VerdictValue.SAFE,
    VerdictValue.PROCESS_COMPLIANT,
}


class ReasoningStep(StrictBaseModel):
    step_id: str = id_field("Reasoning step identifier.")
    claim: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    strength: EvidenceStrength
    limitations: list[str] = Field(default_factory=list)


class Uncertainty(StrictBaseModel):
    kind: str = Field(min_length=1)
    description: str = Field(min_length=1)
    affected_refs: list[str] = Field(default_factory=list)
    forces_unknown: bool


class CalibrationRef(StrictBaseModel):
    calibration_id: str = id_field("Calibration record identifier.")
    family: str = Field(min_length=1)
    version: str = Field(min_length=1)
    ece: float | None = Field(default=None, ge=0.0)


class Verdict(StrictBaseModel):
    schema_family: Literal["verdict"] = "verdict"
    schema_version: str = SCHEMA_VERSION
    verdict_id: str = id_field("Verdict identifier.")
    workflow: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    verdict: VerdictValue
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_bundle_id: str = Field(min_length=1)
    run_record_id: str | None = None
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    uncertainty: list[Uncertainty] = Field(default_factory=list)
    recommended_action: str = Field(min_length=1)
    policy_action: PolicyAction
    calibration: CalibrationRef | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def validate_unknown_reasoning(self) -> "Verdict":
        if self.verdict == VerdictValue.UNKNOWN and not self.uncertainty:
            raise ValueError("unknown verdicts require uncertainty reasons")
        if any(step.strength == EvidenceStrength.CALIBRATED_MODEL for step in self.reasoning_chain) and not self.calibration:
            raise ValueError("calibrated model evidence requires calibration metadata")
        return self


def validate_verdict_against_bundle(verdict: Verdict, bundle: EvidenceBundle) -> None:
    if verdict.evidence_bundle_id != bundle.bundle_id:
        raise ValueError("verdict evidence_bundle_id must match bundle.bundle_id")
    if verdict.verdict in POSITIVE_VERDICTS and bundle.has_only_soft_llm_support():
        raise ValueError("positive verdicts cannot be supported only by soft LLM evidence")
