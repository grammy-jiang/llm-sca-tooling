"""Deterministic hindsight relabeller."""

from __future__ import annotations

from llm_sca_tooling.memory.models import (
    HindsightLabel,
    ReviewState,
    TrajectoryOutcome,
    TrajectoryRecord,
    TrajectoryUtility,
)
from llm_sca_tooling.memory.relabelling.interface import HindsightRelabellerInterface


class NullHindsightRelabeller(HindsightRelabellerInterface):
    model_id = "null"
    version = "phase17-null"

    def relabel(
        self, trajectory: TrajectoryRecord, candidate_goal: str
    ) -> HindsightLabel:
        return HindsightLabel(
            trajectory_id=trajectory.trajectory_id,
            original_outcome=trajectory.outcome,
            relabelled_goal=candidate_goal,
            relabelled_outcome=TrajectoryOutcome.RELABELLED,
            relabelled_utility=TrajectoryUtility.MEDIUM,
            confidence="unknown",
            evidence_refs=[trajectory.source_run_id],
            generator_model=self.model_id,
            review_state=ReviewState.UNREVIEWED,
        )
