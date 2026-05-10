"""Retention policy primitives for operational ledgers."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, parse_utc_ts


class RetentionAction(StrEnum):
    KEEP = "keep"
    EXPORT = "export"
    DELETE = "delete"
    REVIEW = "review"


class RetentionPolicy(StrictBaseModel):
    policy_id: str = Field(default="retention:phase19", min_length=1)
    operational_record_days: int = Field(default=90, ge=1)
    run_record_days: int = Field(default=180, ge=1)
    incident_days: int = Field(default=365, ge=1)
    export_before_delete: bool = True
    allow_delete: bool = False


class RetentionDecision(StrictBaseModel):
    record_id: str = Field(min_length=1)
    action: RetentionAction
    reason: str = Field(min_length=1)
    age_days: int | None = None


class RetentionPolicyEvaluator:
    def __init__(self, policy: RetentionPolicy) -> None:
        self.policy = policy

    def evaluate_records(
        self,
        records: list[JsonObject],
        *,
        now_ts: str,
        timestamp_field: str = "created_ts",
        id_field: str = "record_id",
        retention_days: int | None = None,
    ) -> list[RetentionDecision]:
        now = parse_utc_ts(now_ts)
        allowed_age = timedelta(
            days=retention_days or self.policy.operational_record_days
        )
        decisions: list[RetentionDecision] = []
        for index, record in enumerate(records):
            record_id = str(record.get(id_field) or f"record:{index}")
            raw_ts = record.get(timestamp_field)
            if not isinstance(raw_ts, str):
                decisions.append(
                    RetentionDecision(
                        record_id=record_id,
                        action=RetentionAction.REVIEW,
                        reason=f"missing timestamp field: {timestamp_field}",
                    )
                )
                continue
            age = now - parse_utc_ts(raw_ts)
            age_days = max(age.days, 0)
            if age <= allowed_age:
                decisions.append(
                    RetentionDecision(
                        record_id=record_id,
                        action=RetentionAction.KEEP,
                        reason="within retention window",
                        age_days=age_days,
                    )
                )
                continue
            if self.policy.export_before_delete:
                action = RetentionAction.EXPORT
                reason = "expired record requires export before deletion"
            elif self.policy.allow_delete:
                action = RetentionAction.DELETE
                reason = "expired record may be deleted under approved policy"
            else:
                action = RetentionAction.REVIEW
                reason = "expired record requires human deletion approval"
            decisions.append(
                RetentionDecision(
                    record_id=record_id,
                    action=action,
                    reason=reason,
                    age_days=age_days,
                )
            )
        return decisions
