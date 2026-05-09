from __future__ import annotations

import pytest

from llm_sca_tooling.operations.budget import BudgetMonitor
from llm_sca_tooling.operations.run_records import RunRecordWriter


def test_budget_monitor_reports_warning_and_hard_stop() -> None:
    monitor = BudgetMonitor(tokens_limit=10)
    assert monitor.record_tokens(8).status == "soft_warning"
    assert monitor.record_tokens(2).status == "hard_stop"


def test_run_record_writer_lifecycle(run_record_writer: RunRecordWriter) -> None:
    run_id = run_record_writer.create_run(
        workflow="demo",
        repos=["repo:demo"],
        model_backend="none",
        policy_id="phase0",
        permission_profile="read-only",
        context_budget=100,
        redaction_policy="redacted",
    )
    event_id = run_record_writer.append_event(
        run_id, "tool_call", "tool", "execution", "allow"
    )
    run_record_writer.close_run(
        run_id,
        "complete",
        final_verdict_id="verdict:1",
        harness_condition_id="harness:1",
    )
    run = run_record_writer.get_run(run_id)
    assert run is not None
    assert run.status == "complete"
    assert run.events[0]["event_id"] == event_id
    with pytest.raises(RuntimeError):
        run_record_writer.append_event(
            run_id, "tool_call", "tool", "execution", "allow"
        )
