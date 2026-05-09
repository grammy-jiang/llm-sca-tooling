"""Harness readiness, drift, and stage assessment models."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import SCHEMA_VERSION, StrictBaseModel, id_field
from llm_sca_tooling.schemas.enums import DriftClassification, HarnessStage, Severity
from llm_sca_tooling.schemas.governance import WaiverRef
from llm_sca_tooling.schemas.provenance import Provenance, RepoRef


class ReadinessAxis(StrEnum):
    AGENT_CONFIG = "agent_config"
    DOCUMENTATION = "documentation"
    CI_CD = "ci_cd"
    CODE_STRUCTURE = "code_structure"
    SECURITY = "security"


class AxisScore(StrictBaseModel):
    axis: ReadinessAxis
    score: int = Field(ge=0, le=5)
    evidence_refs: list[str] = Field(default_factory=list)


class ThresholdResult(StrictBaseModel):
    target_stage: HarnessStage
    passed: bool
    reason: str = Field(min_length=1)


class NoRegressionResult(StrictBaseModel):
    passed: bool
    waiver_id: str | None = None
    incident_id: str | None = None
    reason: str = Field(min_length=1)


class HarnessStageAssessment(StrictBaseModel):
    assessment_id: str = id_field("Harness stage assessment identifier.")
    repo: RepoRef
    stage: HarnessStage
    detected_controls: list[str] = Field(default_factory=list)
    missing_controls: list[str] = Field(default_factory=list)
    next_stage_controls: list[str] = Field(default_factory=list)
    blocking_findings: list[str] = Field(default_factory=list)
    provenance: Provenance


class DriftFinding(StrictBaseModel):
    drift_id: str = id_field("Drift finding identifier.")
    target_ref: str = Field(min_length=1)
    classification: DriftClassification
    severity: Severity
    description: str = Field(min_length=1)
    blocks_release: bool
    recommended_action: str = Field(min_length=1)
    provenance: Provenance

    @model_validator(mode="after")
    def validate_relaxed_blocks(self) -> "DriftFinding":
        if self.classification == DriftClassification.RELAXED and not self.blocks_release:
            raise ValueError("relaxed drift must block release unless reviewed externally")
        return self


class AIReadinessReport(StrictBaseModel):
    schema_family: Literal["readiness"] = "readiness"
    schema_version: str = SCHEMA_VERSION
    readiness_report_id: str = id_field("Readiness report identifier.")
    repo: RepoRef
    stage: HarnessStage
    total_score: int = Field(ge=0, le=25)
    axis_scores: list[AxisScore]
    threshold_result: ThresholdResult
    no_regression_result: NoRegressionResult
    missing_controls: list[str] = Field(default_factory=list)
    waivers: list[WaiverRef] = Field(default_factory=list)
    history_refs: list[str] = Field(default_factory=list)
    provenance: Provenance

    @model_validator(mode="after")
    def validate_scores(self) -> "AIReadinessReport":
        axes = {axis.axis for axis in self.axis_scores}
        if axes != set(ReadinessAxis):
            raise ValueError("readiness report must include exactly one score for each axis")
        calculated = sum(axis.score for axis in self.axis_scores)
        if calculated != self.total_score:
            raise ValueError("total_score must equal the sum of axis_scores")
        return self


class ReadinessAxisHistory(StrictBaseModel):
    history_id: str = id_field("Readiness axis history identifier.")
    repo: RepoRef
    axis: ReadinessAxis
    previous_score: int = Field(ge=0, le=5)
    current_score: int = Field(ge=0, le=5)
    delta: int
    source_report_id: str = Field(min_length=1)
    waiver_id: str | None = None
    incident_id: str | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def validate_delta(self) -> "ReadinessAxisHistory":
        if self.delta != self.current_score - self.previous_score:
            raise ValueError("delta must equal current_score - previous_score")
        if self.delta < 0 and not (self.waiver_id or self.incident_id):
            raise ValueError("readiness regressions require waiver or incident linkage")
        return self
