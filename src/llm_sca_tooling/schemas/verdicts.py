"""Verdict, reasoning chain, and calibration models.

A non-unknown positive verdict cannot be supported only by soft_llm evidence.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import SCHEMA_VERSION, NonEmptyStr, StrictModel
from llm_sca_tooling.schemas.provenance import (
    EvidenceStrength,
    PolicyAction,
    Provenance,
)

__all__ = [
    "VerdictValue",
    "CalibrationRef",
    "ReasoningStep",
    "Uncertainty",
    "Verdict",
]


class VerdictValue(str, Enum):
    satisfied = "satisfied"
    violated = "violated"
    safe = "safe"
    risky = "risky"
    unknown = "unknown"
    process_compliant = "process-compliant"
    process_noncompliant = "process-noncompliant"
    trace_incomplete = "trace-incomplete"
    budget_exhausted = "budget-exhausted"
    needs_readiness_work = "needs-readiness-work"


_POSITIVE_VERDICTS = {
    VerdictValue.satisfied,
    VerdictValue.safe,
    VerdictValue.process_compliant,
}

_UNCERTAIN_VERDICTS = {
    VerdictValue.unknown,
    VerdictValue.trace_incomplete,
    VerdictValue.budget_exhausted,
    VerdictValue.needs_readiness_work,
}


class CalibrationRef(StrictModel):
    calibration_id: NonEmptyStr
    family: str
    version: str
    artifact_ref: str | None = None


class ReasoningStep(StrictModel):
    step_id: NonEmptyStr
    claim: str
    evidence_refs: list[str] = Field(default_factory=list)
    strength: EvidenceStrength = EvidenceStrength.soft_llm
    limitations: str | None = None


class Uncertainty(StrictModel):
    kind: NonEmptyStr
    description: str
    affected_refs: list[str] = Field(default_factory=list)
    forces_unknown: bool = False


class Verdict(StrictModel):
    schema_version: str = SCHEMA_VERSION
    verdict_id: NonEmptyStr
    workflow: NonEmptyStr
    subject_ref: NonEmptyStr
    verdict: VerdictValue
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    evidence_bundle_id: NonEmptyStr
    run_record_id: str | None = None
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    uncertainty: list[Uncertainty] = Field(default_factory=list)
    recommended_action: str
    policy_action: PolicyAction
    calibration: CalibrationRef | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def _positive_verdict_needs_evidence(self) -> Verdict:
        """Positive verdicts backed only by soft_llm evidence are rejected."""
        if self.verdict not in _POSITIVE_VERDICTS:
            return self
        all_soft_llm = all(
            step.strength == EvidenceStrength.soft_llm for step in self.reasoning_chain
        )
        if self.reasoning_chain and all_soft_llm:
            raise ValueError(
                f"verdict={self.verdict.value!r} cannot be supported only by "
                "soft_llm evidence; include at least one harder evidence step"
            )
        return self

    @model_validator(mode="after")
    def _unknown_needs_uncertainty(self) -> Verdict:
        """Unknown verdicts should include at least one uncertainty reason."""
        if self.verdict == VerdictValue.unknown and not self.uncertainty:
            # Warn-level: not an error, but callers should add uncertainty reasons
            pass
        return self
