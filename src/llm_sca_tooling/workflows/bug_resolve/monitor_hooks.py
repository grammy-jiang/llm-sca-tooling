"""Monitor hooks for the bug-resolve workflow."""

from __future__ import annotations

import time

from llm_sca_tooling.workflows.bug_resolve.config import WorkflowConfig
from llm_sca_tooling.workflows.bug_resolve.models import (
    MonitorEvent,
    MonitorType,
    StageName,
)


class MonitorState:
    """Mutable monitor counters tracked across the workflow lifetime."""

    def __init__(self, *, start_ts: float | None = None) -> None:
        self.start_ts = start_ts if start_ts is not None else time.monotonic()
        self.tokens_used: int = 0
        self.context_tokens_used: int = 0
        self.consecutive_gate_failures: int = 0
        self.last_failed_gate: str | None = None

    def add_tokens(self, count: int) -> None:
        if count > 0:
            self.tokens_used += count

    def add_context_tokens(self, count: int) -> None:
        if count > 0:
            self.context_tokens_used += count


def check_doom_loop(
    *, run_id: str, stage: StageName, loop_count: int, config: WorkflowConfig
) -> MonitorEvent | None:
    if loop_count >= config.max_repair_loops:
        return MonitorEvent(
            run_id=run_id,
            monitor_type=MonitorType.DOOM_LOOP_CANDIDATE,
            stage=stage,
            loop_count=loop_count,
            detail=f"max_repair_loops={config.max_repair_loops} reached",
            severity="error",
            action_taken="transition_to_failed",
        )
    return None


def check_repeated_failing_gate(
    *,
    run_id: str,
    stage: StageName,
    state: MonitorState,
    failing_gate: str | None,
) -> MonitorEvent | None:
    if failing_gate is None:
        state.consecutive_gate_failures = 0
        state.last_failed_gate = None
        return None
    if failing_gate == state.last_failed_gate:
        state.consecutive_gate_failures += 1
    else:
        state.consecutive_gate_failures = 1
        state.last_failed_gate = failing_gate
    if state.consecutive_gate_failures >= 5:
        return MonitorEvent(
            run_id=run_id,
            monitor_type=MonitorType.REPEATED_FAILING_GATE,
            stage=stage,
            loop_count=state.consecutive_gate_failures,
            detail=f"gate {failing_gate} failed five times in a row",
            severity="error",
            action_taken="transition_to_completed_no_fix",
        )
    return None


def check_budget(
    *,
    run_id: str,
    stage: StageName,
    state: MonitorState,
    config: WorkflowConfig,
    now_ts: float | None = None,
) -> list[MonitorEvent]:
    events: list[MonitorEvent] = []
    if state.context_tokens_used >= config.context_budget:
        events.append(
            MonitorEvent(
                run_id=run_id,
                monitor_type=MonitorType.CONTEXT_BUDGET_HARD_STOP,
                stage=stage,
                loop_count=0,
                detail=f"context_tokens_used={state.context_tokens_used}",
                severity="error",
                action_taken="transition_to_budget_exhausted",
            )
        )
    if state.tokens_used >= config.token_budget:
        events.append(
            MonitorEvent(
                run_id=run_id,
                monitor_type=MonitorType.TOKEN_BUDGET_HARD_STOP,
                stage=stage,
                loop_count=0,
                detail=f"tokens_used={state.tokens_used}",
                severity="error",
                action_taken="transition_to_budget_exhausted",
            )
        )
    current = now_ts if now_ts is not None else time.monotonic()
    if (current - state.start_ts) >= config.wall_clock_budget_seconds:
        events.append(
            MonitorEvent(
                run_id=run_id,
                monitor_type=MonitorType.WALL_CLOCK_BUDGET_HARD_STOP,
                stage=stage,
                loop_count=0,
                detail=(
                    f"wall_seconds={current - state.start_ts:.1f} "
                    f">= limit={config.wall_clock_budget_seconds}"
                ),
                severity="error",
                action_taken="transition_to_budget_exhausted",
            )
        )
    return events


def check_stale_snapshot(
    *,
    run_id: str,
    stage: StageName,
    investigation_snapshot: str | None,
    current_snapshot: str | None,
) -> MonitorEvent | None:
    if not investigation_snapshot or not current_snapshot:
        return None
    if investigation_snapshot != current_snapshot:
        return MonitorEvent(
            run_id=run_id,
            monitor_type=MonitorType.STALE_SNAPSHOT_DETECTED_BEFORE_FINAL_REPORT,
            stage=stage,
            loop_count=0,
            detail=(
                f"investigation_snapshot={investigation_snapshot} "
                f"current_snapshot={current_snapshot}"
            ),
            severity="warning",
            action_taken="add_uncertainty_note",
        )
    return None


__all__ = [
    "MonitorState",
    "check_budget",
    "check_doom_loop",
    "check_repeated_failing_gate",
    "check_stale_snapshot",
]
