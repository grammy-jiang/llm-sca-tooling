"""NullHindsightRelabeller — deterministic test double (no LLM)."""

from __future__ import annotations

import uuid

from llm_sca_tooling.memory.models import (
    HindsightLabel,
    TrajectoryRecord,
)
from llm_sca_tooling.memory.store import MemoryStore


class NullHindsightRelabeller:
    model_id = "null"
    version = "phase17.v1"

    def relabel(
        self,
        trajectory: TrajectoryRecord,
        candidate_goal: str,
    ) -> HindsightLabel:
        relabelled_outcome = (
            "resolved" if trajectory.outcome == "no_fix_found" else trajectory.outcome
        )
        return HindsightLabel(
            trajectory_id=trajectory.trajectory_id,
            original_outcome=trajectory.outcome,
            relabelled_goal=candidate_goal,
            relabelled_outcome=relabelled_outcome,
            relabelled_utility="medium",
            confidence="unknown",
            generator_model=self.model_id,
            review_state="unreviewed",
        )

    def create_relabelled_record(
        self,
        trajectory: TrajectoryRecord,
        label: HindsightLabel,
        store: MemoryStore,
    ) -> TrajectoryRecord:
        """Store relabelled trajectory as NEW record; original unchanged."""
        new_record = trajectory.model_copy(
            update={
                "trajectory_id": f"relabelled:{uuid.uuid4().hex[:8]}",
                "outcome": label.relabelled_outcome,
                "utility": label.relabelled_utility,
                "relabelled": True,
                "hindsight_label": label.relabelled_goal,
                "hindsight_label_confidence": label.confidence,
                "review_state": "unreviewed",
            }
        )
        store.put_trajectory(new_record)
        return new_record
