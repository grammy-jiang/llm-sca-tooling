"""Misalignment guard — rejects high-similarity/low-utility records."""

from __future__ import annotations

from llm_sca_tooling.evaluation.models import now_ts
from llm_sca_tooling.memory.models import CoarseHint, TrajectoryRecord


def apply_misalignment_guard(
    trajectory: TrajectoryRecord,
    similarity_score: float,
    *,
    high_similarity_threshold: float = 0.85,
) -> tuple[bool, str | None]:
    """Return (rejected, reason). Rejected records are visible but not active."""
    # Expired records
    if trajectory.expiry_ts and trajectory.expiry_ts < now_ts():
        return True, "expired"
    # Unreviewed records
    if trajectory.review_state == "unreviewed":
        return True, "unreviewed"
    # Superseded records
    if trajectory.review_state == "superseded":
        return True, "superseded"
    # High-similarity / low-utility
    if similarity_score >= high_similarity_threshold and trajectory.utility == "low":
        return True, f"high_similarity_low_utility:score={similarity_score:.2f}"
    return False, None


def build_coarse_hint(
    trajectory: TrajectoryRecord,
    similarity_score: float,
    fl_class_match: bool = False,
) -> CoarseHint:
    rejected, reason = apply_misalignment_guard(trajectory, similarity_score)
    return CoarseHint(
        trajectory_id=trajectory.trajectory_id,
        issue_class=trajectory.issue_class,
        outcome=trajectory.outcome,
        utility=trajectory.utility,
        fl_class_match=fl_class_match,
        confidence="heuristic",
        rejected=rejected,
        rejection_reason=reason,
    )
