"""Evo-Memory style compaction: promote/demote/expire."""

from __future__ import annotations

from llm_sca_tooling.evaluation.models import now_ts
from llm_sca_tooling.memory.models import (
    EvictionPolicy,
    MemoryCompactionReport,
    TrajectoryRecord,
)
from llm_sca_tooling.memory.store import MemoryStore

_UTILITY_MAP = {"high": 1.0, "medium": 0.5, "low": 0.1, "unknown": 0.3}


def _compute_utility_score(record: TrajectoryRecord, policy: EvictionPolicy) -> float:
    base = _UTILITY_MAP.get(record.utility, 0.3)
    outcome_bonus = 0.2 if record.outcome in {"resolved", "resolved_with_risk"} else 0.0
    relabelled_penalty = policy.relabelled_penalty if record.relabelled else 0.0
    return max(0.0, min(1.0, base + outcome_bonus - relabelled_penalty))


def compact(
    repo_id: str,
    store: MemoryStore,
    policy: EvictionPolicy,
    *,
    dry_run: bool = False,
) -> MemoryCompactionReport:
    trajectories = store.all_trajectories(repo_id=repo_id)
    initial = len(trajectories)
    promoted = demoted = expired = 0
    now = now_ts()

    for traj in trajectories:
        # Expire
        if traj.expiry_ts and traj.expiry_ts < now:
            expired += 1
            if not dry_run:
                store.update_trajectory(traj.trajectory_id, review_state="expired")
            continue

        score = _compute_utility_score(traj, policy)
        if score >= policy.utility_threshold_keep:
            if traj.utility != "high":
                promoted += 1
                if not dry_run:
                    store.update_trajectory(traj.trajectory_id, utility="high")
        elif score < policy.utility_threshold_demote and traj.utility != "low":
            demoted += 1
            if not dry_run:
                store.update_trajectory(traj.trajectory_id, utility="low")

    # Diversity check
    outcomes = {t.outcome for t in store.all_trajectories(repo_id=repo_id)}
    diversity = len(outcomes)

    final_trajectories = store.all_trajectories(repo_id=repo_id)
    final = len([t for t in final_trajectories if t.review_state != "expired"])
    dist: dict[str, int] = {}
    for t in final_trajectories:
        dist[t.utility] = dist.get(t.utility, 0) + 1

    return MemoryCompactionReport(
        repo_id=repo_id,
        initial_count=initial,
        promoted_count=promoted,
        demoted_count=demoted,
        expired_count=expired,
        final_count=final,
        utility_distribution=dist,
        outcome_diversity_achieved=diversity,
        dry_run=dry_run,
    )
