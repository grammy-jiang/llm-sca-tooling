"""Tests for monitor hooks."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.config import WorkflowConfig
from llm_sca_tooling.workflows.bug_resolve.models import StageName
from llm_sca_tooling.workflows.bug_resolve.monitor_hooks import (
    MonitorState,
    check_budget,
    check_doom_loop,
    check_repeated_failing_gate,
    check_stale_snapshot,
)


def test_doom_loop_fires_at_limit() -> None:
    cfg = WorkflowConfig(max_repair_loops=3)
    e = check_doom_loop(run_id="r1", stage=StageName.REPAIR, loop_count=3, config=cfg)
    assert e is not None
    assert e.severity == "error"


def test_doom_loop_below_limit() -> None:
    cfg = WorkflowConfig(max_repair_loops=3)
    assert (
        check_doom_loop(run_id="r1", stage=StageName.REPAIR, loop_count=2, config=cfg)
        is None
    )


def test_repeated_failing_gate_fires_after_5() -> None:
    state = MonitorState()
    last = None
    for _ in range(5):
        last = check_repeated_failing_gate(
            run_id="r1",
            stage=StageName.GATES,
            state=state,
            failing_gate="sarif",
        )
    assert last is not None


def test_repeated_failing_gate_resets_on_different_gate() -> None:
    state = MonitorState()
    for _ in range(4):
        check_repeated_failing_gate(
            run_id="r1",
            stage=StageName.GATES,
            state=state,
            failing_gate="sarif",
        )
    e = check_repeated_failing_gate(
        run_id="r1",
        stage=StageName.GATES,
        state=state,
        failing_gate="build",
    )
    assert e is None
    assert state.consecutive_gate_failures == 1


def test_repeated_failing_gate_clears_on_none() -> None:
    state = MonitorState()
    state.consecutive_gate_failures = 4
    state.last_failed_gate = "sarif"
    e = check_repeated_failing_gate(
        run_id="r1", stage=StageName.GATES, state=state, failing_gate=None
    )
    assert e is None
    assert state.consecutive_gate_failures == 0


def test_check_budget_context() -> None:
    cfg = WorkflowConfig(context_budget=10)
    state = MonitorState()
    state.add_context_tokens(20)
    events = check_budget(run_id="r1", stage=StageName.REPAIR, state=state, config=cfg)
    assert any(e.monitor_type.value == "context_budget_hard_stop" for e in events)


def test_check_budget_token() -> None:
    cfg = WorkflowConfig(token_budget=10)
    state = MonitorState()
    state.add_tokens(20)
    events = check_budget(run_id="r1", stage=StageName.REPAIR, state=state, config=cfg)
    assert any(e.monitor_type.value == "token_budget_hard_stop" for e in events)


def test_check_budget_wall_clock() -> None:
    cfg = WorkflowConfig(wall_clock_budget_seconds=1)
    state = MonitorState(start_ts=0.0)
    events = check_budget(
        run_id="r1",
        stage=StageName.REPAIR,
        state=state,
        config=cfg,
        now_ts=10.0,
    )
    assert any(e.monitor_type.value == "wall_clock_budget_hard_stop" for e in events)


def test_check_budget_within() -> None:
    cfg = WorkflowConfig()
    events = check_budget(
        run_id="r1",
        stage=StageName.REPAIR,
        state=MonitorState(start_ts=0.0),
        config=cfg,
        now_ts=1.0,
    )
    assert events == []


def test_stale_snapshot_fires() -> None:
    e = check_stale_snapshot(
        run_id="r1",
        stage=StageName.TRAJECTORY,
        investigation_snapshot="A",
        current_snapshot="B",
    )
    assert e is not None


def test_stale_snapshot_equal() -> None:
    assert (
        check_stale_snapshot(
            run_id="r1",
            stage=StageName.TRAJECTORY,
            investigation_snapshot="A",
            current_snapshot="A",
        )
        is None
    )


def test_stale_snapshot_missing_inputs() -> None:
    assert (
        check_stale_snapshot(
            run_id="r1",
            stage=StageName.TRAJECTORY,
            investigation_snapshot=None,
            current_snapshot="B",
        )
        is None
    )
