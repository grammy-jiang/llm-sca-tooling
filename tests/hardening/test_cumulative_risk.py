"""Tests for CumulativeRiskMonitor."""

from __future__ import annotations

from llm_sca_tooling.hardening.cumulative_risk import CumulativeRiskMonitor


def _make_monitor(run_id: str = "run1") -> CumulativeRiskMonitor:
    return CumulativeRiskMonitor(
        run_id=run_id, thresholds={"repeated_identical_tool_calls": 2}
    )


def test_no_events_initially() -> None:
    mon = _make_monitor()
    assert mon.events() == []


def test_repeated_tool_calls_emits_event() -> None:
    mon = _make_monitor()
    for _ in range(3):
        mon.record_tool_call("read_file", {"path": "/foo"})
    assert len(mon.events()) >= 1
    assert any(e.pattern_type == "repeated_identical_tool_calls" for e in mon.events())


def test_distinct_tool_calls_no_event() -> None:
    mon = _make_monitor()
    mon.record_tool_call("read_file", {"path": "/foo"})
    mon.record_tool_call("read_file", {"path": "/bar"})
    assert len(mon.events()) == 0


def test_gate_fail_emits_event() -> None:
    mon = CumulativeRiskMonitor(
        run_id="run2", thresholds={"repeated_failing_gate_no_change": 2}
    )
    for _ in range(3):
        mon.record_gate_result("gate1", passed=False, evidence_changed=False)
    assert any(
        e.pattern_type == "repeated_failing_gate_no_change" for e in mon.events()
    )


def test_budget_hard_stop_emits_event() -> None:
    mon = CumulativeRiskMonitor(
        run_id="run3", thresholds={"budget_exhaustion_pattern": 1}
    )
    mon.record_budget_hard_stop()
    mon.record_budget_hard_stop()
    assert any(e.pattern_type == "budget_exhaustion_pattern" for e in mon.events())
