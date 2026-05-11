"""Monitor hooks for loop detection and budget enforcement."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import MonitorEvent, WorkflowState


def check_budget(
    state: WorkflowState,
    *,
    tokens_used: int,
    token_budget: int,
) -> MonitorEvent | None:
    if tokens_used >= token_budget:
        event = MonitorEvent(
            run_id=state.run_id,
            monitor_type="token_budget_hard_stop",
            stage=state.stage,
            loop_count=state.loop_count,
            detail=f"tokens_used={tokens_used} >= budget={token_budget}",
            severity="error",
            action_taken="transition_budget_exhausted",
        )
        state.monitor_events.append(event.model_dump(mode="json"))
        state.status = "budget_exhausted"
        return event
    return None


def check_doom_loop(
    state: WorkflowState,
    *,
    max_loops: int,
) -> MonitorEvent | None:
    if state.loop_count >= max_loops:
        event = MonitorEvent(
            run_id=state.run_id,
            monitor_type="doom_loop_candidate",
            stage=state.stage,
            loop_count=state.loop_count,
            detail=f"loop_count={state.loop_count} >= max_repair_loops={max_loops}",
            severity="error",
            action_taken="transition_failed",
        )
        state.monitor_events.append(event.model_dump(mode="json"))
        state.status = "failed"
        return event
    return None


def check_stale_snapshot(
    state: WorkflowState,
    *,
    snapshot_id: str | None,
    current_snapshot_id: str | None,
) -> MonitorEvent | None:
    if snapshot_id != current_snapshot_id:
        event = MonitorEvent(
            run_id=state.run_id,
            monitor_type="stale_snapshot_detected_before_final_report",
            stage=state.stage,
            detail=f"investigate_snapshot={snapshot_id} current={current_snapshot_id}",
            severity="warning",
            action_taken="flagged_in_report",
        )
        state.monitor_events.append(event.model_dump(mode="json"))
        return event
    return None
