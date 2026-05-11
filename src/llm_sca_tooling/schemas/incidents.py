"""Incident and promotion candidate models."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import NonEmptyStr, StrictModel
from llm_sca_tooling.schemas.provenance import Provenance

__all__ = [
    "IncidentSeverity",
    "IncidentStatus",
    "PromotionTarget",
    "ReviewState",
    "Incident",
    "PromotionCandidate",
]


class IncidentSeverity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class IncidentStatus(str, Enum):
    open = "open"
    contained = "contained"
    closed = "closed"


class PromotionTarget(str, Enum):
    memory = "memory"
    detector = "detector"
    eval_regression = "eval_regression"
    static_analysis_rule = "static_analysis_rule"
    readiness_task = "readiness_task"
    governance_policy = "governance_policy"


class ReviewState(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class Incident(StrictModel):
    incident_id: NonEmptyStr
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.open
    title: str
    description: str = ""
    source_run_ids: list[str] = Field(default_factory=list)
    source_event_ids: list[str] = Field(default_factory=list)
    evidence_links: list[str] = Field(default_factory=list)
    detector_follow_up: str | None = None
    eval_follow_up: str | None = None
    reviewer: str | None = None
    closed_ts: str | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def _requires_source_links(self) -> Incident:
        if not self.source_run_ids and not self.source_event_ids:
            raise ValueError(
                "incident must reference at least one source_run_id or source_event_id"
            )
        return self

    @model_validator(mode="after")
    def _closed_needs_reviewer(self) -> Incident:
        if self.status == IncidentStatus.closed and self.reviewer is None:
            raise ValueError("closed incident must have reviewer metadata")
        return self


class PromotionCandidate(StrictModel):
    promotion_id: NonEmptyStr
    source_run_id: NonEmptyStr
    source_event_ids: list[str] = Field(default_factory=list)
    target_type: PromotionTarget
    target_ref: str | None = None
    lesson_summary: str
    review_state: ReviewState = ReviewState.pending
    owner: NonEmptyStr
    expires_ts: str | None = None
    rollback_path: str | None = None
    evidence_links: list[str] = Field(default_factory=list)
    provenance: Provenance

    @model_validator(mode="after")
    def _requires_source_links(self) -> PromotionCandidate:
        if not self.source_run_id:
            raise ValueError("promotion candidate must reference a source_run_id")
        return self
