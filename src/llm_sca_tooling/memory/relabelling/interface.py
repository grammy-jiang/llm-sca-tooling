"""Hindsight relabelling interface and policy-guarded storage (phase 17 §9).

A relabelled trajectory is always stored as a *new* record marked
``relabelled: true`` with ``review_state: unreviewed``; the original record is
never modified. Relabelling output is a labelled hypothesis, not a fact — it
enters the retrieval pool only after human promotion to ``approved``.
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from llm_sca_tooling.memory.models import (
    HindsightLabel,
    MemoryOptInPolicy,
    TrajectoryRecord,
)
from llm_sca_tooling.memory.store import MemoryStore


class RelabellingNotAllowedError(Exception):
    """Raised when the memory policy does not opt in to hindsight relabelling."""


@runtime_checkable
class HindsightRelabellerInterface(Protocol):
    """LLM boundary for Agent-HER-style hindsight relabelling."""

    model_id: str
    version: str

    def relabel(
        self,
        trajectory: TrajectoryRecord,
        candidate_goal: str,
    ) -> HindsightLabel: ...


def store_relabelled_trajectory(
    trajectory: TrajectoryRecord,
    label: HindsightLabel,
    store: MemoryStore,
) -> TrajectoryRecord:
    """Store the relabelled trajectory as a new record; original unchanged."""
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


def relabel_and_store(
    relabeller: HindsightRelabellerInterface,
    trajectory: TrajectoryRecord,
    *,
    candidate_goal: str,
    store: MemoryStore,
    policy: MemoryOptInPolicy,
) -> TrajectoryRecord:
    """Relabel a trajectory under policy guard and store the hypothesis."""
    if not policy.allow_hindsight_relabelling:
        raise RelabellingNotAllowedError(
            "memory policy does not allow hindsight relabelling "
            "(allow_hindsight_relabelling is false)"
        )
    label = relabeller.relabel(trajectory, candidate_goal)
    return store_relabelled_trajectory(trajectory, label, store)
