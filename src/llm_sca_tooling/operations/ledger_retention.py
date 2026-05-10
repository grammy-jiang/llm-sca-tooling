"""Operational ledger retention evaluation."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.privacy.retention_policy import (
    RetentionDecision,
    RetentionPolicy,
    RetentionPolicyEvaluator,
)
from llm_sca_tooling.schemas.base import JsonObject


class LedgerRetentionPolicy(RetentionPolicy):
    ledger_kinds: list[str] = Field(default_factory=list)


class LedgerRetentionService:
    def __init__(self, policy: LedgerRetentionPolicy) -> None:
        self.policy = policy
        self.evaluator = RetentionPolicyEvaluator(policy)

    def evaluate_operational_records(
        self, records: list[JsonObject], *, now_ts: str
    ) -> list[RetentionDecision]:
        filtered = [
            record
            for record in records
            if not self.policy.ledger_kinds
            or str(record.get("kind")) in self.policy.ledger_kinds
        ]
        return self.evaluator.evaluate_records(
            filtered,
            now_ts=now_ts,
            retention_days=self.policy.operational_record_days,
        )
