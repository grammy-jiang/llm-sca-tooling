"""Coarse retriever — issue-class similarity for investigation phase."""

from __future__ import annotations

from llm_sca_tooling.memory.models import CoarseHint
from llm_sca_tooling.memory.retrieval.misalignment_guard import build_coarse_hint
from llm_sca_tooling.memory.store import MemoryStore


def retrieve_coarse(
    issue_text: str,
    repo_id: str,
    store: MemoryStore,
    *,
    max_hints: int = 5,
) -> tuple[list[CoarseHint], list[CoarseHint]]:
    """Return (active_hints, rejected_hints)."""
    trajectories = store.all_trajectories(repo_id=repo_id)
    active: list[CoarseHint] = []
    rejected: list[CoarseHint] = []
    keywords = set(issue_text.lower().split())
    for traj in trajectories:
        sim = _issue_class_similarity(keywords, traj.issue_class)
        hint = build_coarse_hint(traj, sim)
        if hint.rejected:
            rejected.append(hint)
        else:
            active.append(hint)
    active.sort(key=lambda h: h.utility == "high", reverse=True)
    return active[:max_hints], rejected


def _issue_class_similarity(keywords: set[str], issue_class: str) -> float:
    class_words = set(issue_class.lower().split())
    if not class_words:
        return 0.0
    overlap = keywords & class_words
    return len(overlap) / max(len(class_words), 1)
