"""Incident and promotion contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import SCHEMA_VERSION, JsonObject, StrictBaseModel, id_field
from llm_sca_tooling.schemas.enums import Severity, Status
from llm_sca_tooling.schemas.provenance import Provenance


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    MITIGATED = "mitigated"
    CLOSED = "closed"


class TimelineEntry(StrictBaseModel):
    ts: str = Field(min_length=1)
    description: str = Field(min_length=1)
    actor: str | None = None


class Incident(StrictBaseModel):
    schema_family: Literal["incident"] = "incident"
    schema_version: str = SCHEMA_VERSION
    incident_id: str = id_field("Incident identifier.")
    severity: Severity
    status: IncidentStatus
    title: str = Field(min_length=1)
    impact: str = Field(min_length=1)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    root_cause: str | None = None
    containment: str | None = None
    remediation: str | None = None
    evidence_links: list[str] = Field(default_factory=list)
    source_run_ids: list[str] = Field(default_factory=list)
    source_event_ids: list[str] = Field(default_factory=list)
    detector_follow_up: str | None = None
    eval_follow_up: str | None = None
    reviewer: str | None = None
    closed_ts: str | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def validate_incident_links(self) -> "Incident":
        if not (self.source_run_ids or self.source_event_ids):
            raise ValueError("incidents must link to source run or event IDs")
        if self.status == IncidentStatus.CLOSED and not (self.reviewer and self.closed_ts):
            raise ValueError("closed incidents require reviewer and closed_ts")
        return self


class PromotionTargetType(StrEnum):
    MEMORY = "memory"
    DETECTOR = "detector"
    EVAL_REGRESSION = "eval_regression"
    STATIC_ANALYSIS_RULE = "static_analysis_rule"
    READINESS_TASK = "readiness_task"
    GOVERNANCE_POLICY = "governance_policy"


class PromotionReviewState(StrEnum):
    PROPOSED = "proposed"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    PROMOTED = "promoted"


class PromotionCandidate(StrictBaseModel):
    promotion_id: str = id_field("Promotion candidate identifier.")
    source_run_id: str = Field(min_length=1)
    source_event_ids: list[str]
    target_type: PromotionTargetType
    target_ref: str = Field(min_length=1)
    lesson_summary: str = Field(min_length=1)
    review_state: PromotionReviewState
    owner: str = Field(min_length=1)
    expires_ts: str | None = None
    review_due_ts: str | None = None
    rollback_path: str = Field(min_length=1)
    evidence_links: list[str] = Field(default_factory=list)
    provenance: Provenance
    metadata: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_promotion(self) -> "PromotionCandidate":
        if not self.source_event_ids:
            raise ValueError("promotion candidates must link to source event IDs")
        if not (self.expires_ts or self.review_due_ts):
            raise ValueError("promotion candidates require expires_ts or review_due_ts")
        if self.target_type == PromotionTargetType.MEMORY and self.review_state == PromotionReviewState.PROPOSED:
            raise ValueError("unreviewed prose memory is not durable")
        return self
