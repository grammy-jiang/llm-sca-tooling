"""Deterministic fine trajectory retrieval."""

from __future__ import annotations

from llm_sca_tooling.memory.models import FineHint, HintType, TrajectoryRecord
from llm_sca_tooling.memory.retrieval.misalignment_guard import MisalignmentGuard
from llm_sca_tooling.memory.store import MemoryStore


class FineRetriever:
    def __init__(
        self, store: MemoryStore, guard: MisalignmentGuard | None = None
    ) -> None:
        self.store = store
        self.guard = guard or MisalignmentGuard()

    def retrieve(
        self,
        *,
        issue_text: str,
        repo_id: str,
        graph_node_ids: list[str] | None = None,
        max_hints: int = 5,
    ) -> tuple[list[FineHint], list[FineHint]]:
        active: list[FineHint] = []
        rejected: list[FineHint] = []
        requested = set(graph_node_ids or [])
        for record in self.store.list_trajectories(repo_id):
            score = _similarity(issue_text, record, requested)
            reason = self.guard.rejection_reason(record, similarity_score=score)
            hint = FineHint(
                trajectory_id=record.trajectory_id,
                hint_type=_hint_type(record),
                content_snippet=";".join(record.bounded_snippet_ids[:3]),
                graph_node_ids=record.graph_node_ids,
                patch_class=record.patch_class,
                outcome=record.outcome,
                utility=record.utility,
                similarity_score=score,
                misalignment_flag=reason is not None,
                confidence=score,
            )
            if reason:
                rejected.append(hint)
            elif score > 0:
                active.append(hint)
        return active[:max_hints], rejected


def _similarity(
    issue_text: str, record: TrajectoryRecord, requested_nodes: set[str]
) -> float:
    if requested_nodes and requested_nodes.intersection(record.graph_node_ids):
        return 0.95
    if record.issue_class.lower() in issue_text.lower():
        return 0.88
    return 0.0


def _hint_type(record: TrajectoryRecord) -> HintType:
    if record.patch_class:
        return HintType.PATCH_SNIPPET
    if record.fl_decisions:
        return HintType.FL_DECISION
    return HintType.REJECTION_REASON
