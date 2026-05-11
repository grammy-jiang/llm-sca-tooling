"""Fine retriever — FL-class and snippet hints for repair and review."""

from __future__ import annotations

from llm_sca_tooling.memory.models import FineHint
from llm_sca_tooling.memory.retrieval.misalignment_guard import apply_misalignment_guard
from llm_sca_tooling.memory.store import MemoryStore


def retrieve_fine(
    issue_text: str,
    repo_id: str,
    store: MemoryStore,
    *,
    max_hints: int = 5,
) -> tuple[list[FineHint], list[FineHint]]:
    """Return (active_hints, rejected_hints)."""
    trajectories = store.all_trajectories(repo_id=repo_id)
    keywords = set(issue_text.lower().split())
    active: list[FineHint] = []
    rejected: list[FineHint] = []
    for traj in trajectories:
        sim = _fl_similarity(keywords, traj.fl_decisions)
        misaligned, _ = apply_misalignment_guard(traj, sim)
        hint = FineHint(
            trajectory_id=traj.trajectory_id,
            hint_type=_infer_hint_type(traj),
            content_snippet=_extract_snippet(traj),
            graph_node_ids=traj.graph_node_ids[:3],
            patch_class=traj.patch_class,
            outcome=traj.outcome,
            utility=traj.utility,
            similarity_score=sim,
            misalignment_flag=misaligned,
            confidence="heuristic",
        )
        if misaligned:
            rejected.append(hint)
        else:
            active.append(hint)
    active.sort(key=lambda h: h.similarity_score, reverse=True)
    return active[:max_hints], rejected


def _fl_similarity(keywords: set[str], fl_decisions: list[str]) -> float:
    if not fl_decisions:
        return 0.0
    all_words = set(" ".join(fl_decisions).lower().split())
    overlap = keywords & all_words
    return len(overlap) / max(len(all_words), 1)


def _infer_hint_type(traj: object) -> str:
    outcome = getattr(traj, "outcome", "")
    if outcome == "false_positive":
        return "rejection_reason"
    if getattr(traj, "patch_diff_hash", None):
        return "patch_snippet"
    return "fl_decision"


def _extract_snippet(traj: object) -> str:
    fl = getattr(traj, "fl_decisions", [])
    if fl:
        return f"fl_suspect:{fl[0]}"
    patch = getattr(traj, "patch_class", None)
    if patch:
        return f"patch_class:{patch}"
    return "no_snippet"
