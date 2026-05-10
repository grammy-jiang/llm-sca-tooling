"""Deterministic coarse trajectory retrieval."""

from __future__ import annotations

from llm_sca_tooling.memory.models import CoarseHint, TrajectoryRecord
from llm_sca_tooling.memory.retrieval.misalignment_guard import MisalignmentGuard
from llm_sca_tooling.memory.store import MemoryStore


class CoarseRetriever:
    def __init__(
        self, store: MemoryStore, guard: MisalignmentGuard | None = None
    ) -> None:
        self.store = store
        self.guard = guard or MisalignmentGuard()

    def retrieve(
        self, *, issue_text: str, repo_id: str, max_hints: int = 5
    ) -> tuple[list[CoarseHint], list[CoarseHint]]:
        active: list[CoarseHint] = []
        rejected: list[CoarseHint] = []
        for record in self.store.list_trajectories(repo_id):
            score = _similarity(issue_text, record)
            reason = self.guard.rejection_reason(record, similarity_score=score)
            hint = CoarseHint(
                trajectory_id=record.trajectory_id,
                issue_class=record.issue_class,
                outcome=record.outcome,
                utility=record.utility,
                fl_class_match=record.issue_class if score > 0 else "",
                confidence=score,
                rejected=reason is not None,
                rejection_reason=reason or "",
            )
            if reason:
                rejected.append(hint)
            elif score > 0:
                active.append(hint)
        return active[:max_hints], rejected


def _similarity(issue_text: str, record: TrajectoryRecord) -> float:
    lowered = issue_text.lower()
    if record.issue_class.lower() in lowered:
        return 0.9
    if record.issue_text_hash and record.issue_text_hash in issue_text:
        return 1.0
    return 0.0
