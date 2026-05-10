from __future__ import annotations

from llm_sca_tooling.workflows.impl_check.operational_binding import (
    build_operational_binding,
)


def test_build_returns_model() -> None:
    b = build_operational_binding("run:1", "clause:1")
    assert b.run_id == "run:1"
    assert b.clause_id == "clause:1"
    assert b.required_gate_events_present is True


def test_stale_snapshot_flag_propagated() -> None:
    b = build_operational_binding("r", "c", stale_snapshot_flag=True)
    assert b.stale_snapshot_flag is True


def test_required_gate_events_present_propagated() -> None:
    b = build_operational_binding("r", "c", required_gate_events_present=False)
    assert b.required_gate_events_present is False


def test_resource_refs_default_empty() -> None:
    b = build_operational_binding("r", "c")
    assert b.resource_refs == []
    assert b.tool_calls == []
    assert b.gate_results == []


def test_harness_condition_id_set() -> None:
    b = build_operational_binding("r", "c", harness_condition_id="hcs:1")
    assert b.harness_condition_id == "hcs:1"
