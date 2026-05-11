"""Readiness, drift, and stage models."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from llm_sca_tooling.schemas.base import SCHEMA_VERSION, NonEmptyStr, StrictModel
from llm_sca_tooling.schemas.governance import DriftClassification
from llm_sca_tooling.schemas.provenance import Provenance, RepoRef

__all__ = [
    "HarnessStage",
    "ReadinessAxis",
    "AxisScore",
    "HarnessStageAssessment",
    "DriftFinding",
    "AIReadinessReport",
    "ReadinessAxisHistory",
]


class HarnessStage(str, Enum):
    S0 = "S0"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"


class ReadinessAxis(str, Enum):
    agent_config = "agent_config"
    documentation = "documentation"
    ci_cd = "ci_cd"
    code_structure = "code_structure"
    security = "security"


_STAGE_THRESHOLDS: dict[str, tuple[int, int]] = {
    "S0->S1": (5, 1),
    "S1->S2": (12, 2),
    "S2->S3": (18, 3),
    "stable-S3": (22, 4),
}


class AxisScore(StrictModel):
    axis: ReadinessAxis
    score: Annotated[int, Field(ge=0, le=5)]


class HarnessStageAssessment(StrictModel):
    assessment_id: NonEmptyStr
    repo: RepoRef
    stage: HarnessStage
    detected_controls: list[str] = Field(default_factory=list)
    missing_controls: list[str] = Field(default_factory=list)
    next_stage_controls: list[str] = Field(default_factory=list)
    blocking_findings: list[str] = Field(default_factory=list)
    provenance: Provenance


class DriftFinding(StrictModel):
    drift_id: NonEmptyStr
    target_ref: NonEmptyStr
    classification: DriftClassification
    severity: str = "warning"
    description: str
    blocks_release: bool
    recommended_action: str | None = None
    provenance: Provenance

    @field_validator("blocks_release", mode="before")
    @classmethod
    def _relaxed_always_blocks(cls, v: object, info: object) -> object:
        return v


class WaiverRecord(StrictModel):
    waiver_id: NonEmptyStr
    axis: ReadinessAxis | None = None
    reason: str
    owner: NonEmptyStr
    review_due_ts: NonEmptyStr


class AIReadinessReport(StrictModel):
    schema_version: str = SCHEMA_VERSION
    readiness_report_id: NonEmptyStr
    repo: RepoRef
    stage: HarnessStage
    total_score: Annotated[int, Field(ge=0, le=25)]
    axis_scores: list[AxisScore]
    threshold_result: str = "unknown"
    no_regression_result: str = "unknown"
    missing_controls: list[str] = Field(default_factory=list)
    waivers: list[WaiverRecord] = Field(default_factory=list)
    history_refs: list[str] = Field(default_factory=list)
    provenance: Provenance

    @model_validator(mode="after")
    def _total_matches_axis_sum(self) -> AIReadinessReport:
        computed = sum(s.score for s in self.axis_scores)
        if computed != self.total_score:
            raise ValueError(
                f"total_score {self.total_score} != sum of axis scores {computed}"
            )
        return self

    def meets_stage_threshold(self, transition: str) -> bool:
        """Check whether this report meets a stage-gate threshold."""
        if transition not in _STAGE_THRESHOLDS:
            return False
        min_total, min_per_axis = _STAGE_THRESHOLDS[transition]
        if self.total_score < min_total:
            return False
        return all(s.score >= min_per_axis for s in self.axis_scores)


class ReadinessAxisHistory(StrictModel):
    history_id: NonEmptyStr
    repo: RepoRef
    axis: ReadinessAxis
    previous_score: Annotated[int, Field(ge=0, le=5)]
    current_score: Annotated[int, Field(ge=0, le=5)]
    delta: int
    source_report_id: NonEmptyStr
    waiver_id: str | None = None
    incident_id: str | None = None
    provenance: Provenance
