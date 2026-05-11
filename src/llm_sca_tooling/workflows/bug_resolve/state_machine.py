"""Workflow state transitions."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import MonitorEvent, WorkflowState

_STAGES = [
    "load",
    "investigate",
    "repair",
    "dryrun",
    "gates",
    "patch_risk",
    "blast_radius",
    "scope_audit",
    "operational_review",
    "trajectory",
]


def advance(state: WorkflowState, to: str) -> WorkflowState:
    state.stage_history.append(state.stage)
    state.stage = to
    return state


def transition_budget_exhausted(state: WorkflowState, detail: str) -> WorkflowState:
    event = MonitorEvent(
        run_id=state.run_id,
        monitor_type="context_budget_hard_stop",
        stage=state.stage,
        loop_count=state.loop_count,
        detail=detail,
        severity="error",
        action_taken="transition_budget_exhausted",
    )
    state.monitor_events.append(event.model_dump(mode="json"))
    state.status = "budget_exhausted"
    return state


def check_doom_loop(state: WorkflowState, config_max: int) -> MonitorEvent | None:
    if state.loop_count >= config_max:
        return MonitorEvent(
            run_id=state.run_id,
            monitor_type="doom_loop_candidate",
            stage=state.stage,
            loop_count=state.loop_count,
            detail=f"loop_count={state.loop_count} reached max={config_max}",
            severity="error",
            action_taken="transition_failed",
        )
    return None
