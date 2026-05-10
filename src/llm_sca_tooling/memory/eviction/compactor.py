"""Deterministic Evo-Memory-style compaction."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from llm_sca_tooling.memory.models import (
    EvictionPolicy,
    MemoryCompactionReport,
    ReviewState,
    TrajectoryOutcome,
    TrajectoryRecord,
    TrajectoryUtility,
)
from llm_sca_tooling.memory.store import MemoryStore


class MemoryCompactor:
    def __init__(
        self, store: MemoryStore, policy: EvictionPolicy | None = None
    ) -> None:
        self.store = store
        self.policy = policy or EvictionPolicy()

    def compact(
        self, *, repo_id: str | None = None, dry_run: bool = True
    ) -> MemoryCompactionReport:
        records = self.store.list_trajectories(repo_id)
        updated: list[TrajectoryRecord] = []
        promoted = 0
        demoted = 0
        expired = 0
        for record in records:
            new_state = record.review_state
            new_utility = _target_utility(record)
            if record.expiry_ts and _is_expired(record.expiry_ts):
                new_state = ReviewState.EXPIRED
                expired += 1
            elif (
                new_utility is TrajectoryUtility.HIGH
                and record.utility is not TrajectoryUtility.HIGH
            ):
                promoted += 1
            elif (
                new_utility is TrajectoryUtility.LOW
                and record.utility is not TrajectoryUtility.LOW
            ):
                demoted += 1
            if new_state != record.review_state or new_utility != record.utility:
                updated.append(
                    record.model_copy(
                        update={"review_state": new_state, "utility": new_utility}
                    )
                )
        retained = [
            record
            for record in records
            if record.review_state is not ReviewState.EXPIRED
        ]
        overflow = max(0, len(retained) - self.policy.max_trajectories_per_repo)
        if overflow:
            for record in sorted(retained, key=_utility_rank)[:overflow]:
                expired += 1
                updated.append(
                    record.model_copy(update={"review_state": ReviewState.EXPIRED})
                )
        if not dry_run:
            seen: set[str] = set()
            for record in updated:
                if record.trajectory_id in seen:
                    continue
                seen.add(record.trajectory_id)
                self.store.put_trajectory(record)
        final_records = (
            self.store.list_trajectories(repo_id) if not dry_run else records
        )
        report = MemoryCompactionReport(
            report_id=f"memory-compact:{uuid.uuid4().hex}",
            repo_id=repo_id,
            dry_run=dry_run,
            initial_count=len(records),
            promoted_count=promoted,
            demoted_count=demoted,
            expired_count=expired,
            final_count=len(
                [
                    record
                    for record in final_records
                    if record.review_state is not ReviewState.EXPIRED
                ]
            ),
            utility_distribution=_distribution(final_records),
            outcome_diversity_achieved=len(
                {record.outcome for record in final_records}
            ),
            issue_class_coverage_achieved=len(
                {record.issue_class for record in final_records}
            ),
            updated_trajectory_ids=[record.trajectory_id for record in updated],
        )
        self.store.put_compaction_report(report)
        return report


def _target_utility(record: TrajectoryRecord) -> TrajectoryUtility:
    if record.outcome in {
        TrajectoryOutcome.RESOLVED,
        TrajectoryOutcome.RESOLVED_WITH_RISK,
        TrajectoryOutcome.FALSE_POSITIVE,
    }:
        return TrajectoryUtility.HIGH
    if record.outcome in {
        TrajectoryOutcome.NO_FIX_FOUND,
        TrajectoryOutcome.REJECTED_BY_REVIEW,
    }:
        return TrajectoryUtility.LOW
    return record.utility


def _utility_rank(record: TrajectoryRecord) -> int:
    return {
        TrajectoryUtility.LOW: 0,
        TrajectoryUtility.UNKNOWN: 1,
        TrajectoryUtility.MEDIUM: 2,
        TrajectoryUtility.HIGH: 3,
    }[record.utility]


def _distribution(records: list[TrajectoryRecord]) -> dict[str, int]:
    result: dict[str, int] = {}
    for record in records:
        result[record.utility.value] = result.get(record.utility.value, 0) + 1
    return result


def _is_expired(value: str) -> bool:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        UTC
    ) < datetime.now(UTC)
