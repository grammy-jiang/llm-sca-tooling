"""Misalignment guard for retrieved memory."""

from __future__ import annotations

from datetime import UTC, datetime

from llm_sca_tooling.memory.models import (
    ReviewState,
    TrajectoryRecord,
    TrajectoryUtility,
)


class MisalignmentGuard:
    def rejection_reason(
        self, record: TrajectoryRecord, *, similarity_score: float
    ) -> str | None:
        if record.expiry_ts and _is_expired(record.expiry_ts):
            return "expired"
        if record.review_state is ReviewState.UNREVIEWED:
            return "unreviewed"
        if record.review_state is ReviewState.SUPERSEDED:
            return "superseded"
        if record.review_state is ReviewState.EXPIRED:
            return "expired"
        if similarity_score >= 0.85 and record.utility is TrajectoryUtility.LOW:
            return "high_similarity_low_utility"
        return None


def _is_expired(value: str) -> bool:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(UTC) < datetime.now(UTC)
