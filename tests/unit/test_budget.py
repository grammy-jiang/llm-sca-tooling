"""Tests for the budget monitor."""

from __future__ import annotations

import pytest

from llm_sca_tooling.config import BudgetConfig
from llm_sca_tooling.operations.budget import BudgetMonitor


@pytest.fixture()
def tight_budget() -> BudgetMonitor:
    return BudgetMonitor(
        BudgetConfig(
            max_tokens=100, max_tool_calls=5, max_retries=2, max_wall_seconds=3600
        )
    )


def test_initial_status_is_ok(tight_budget: BudgetMonitor) -> None:
    status = tight_budget.check_wall_clock()
    assert status.status == "ok"


def test_record_tokens_returns_status(tight_budget: BudgetMonitor) -> None:
    status = tight_budget.record_tokens(50)
    assert status.tokens_used == 50
    assert status.status == "ok"


def test_soft_warning_at_80_percent(tight_budget: BudgetMonitor) -> None:
    status = tight_budget.record_tokens(81)
    assert status.status == "soft_warning"


def test_hard_stop_at_100_percent(tight_budget: BudgetMonitor) -> None:
    status = tight_budget.record_tokens(100)
    assert status.status == "hard_stop"


def test_hard_stop_above_limit(tight_budget: BudgetMonitor) -> None:
    status = tight_budget.record_tokens(200)
    assert status.status == "hard_stop"


def test_tool_call_limit(tight_budget: BudgetMonitor) -> None:
    for _ in range(5):
        tight_budget.record_tool_call()
    status = tight_budget.record_tool_call()
    assert status.status == "hard_stop"


def test_retry_limit(tight_budget: BudgetMonitor) -> None:
    for _ in range(2):
        tight_budget.record_retry()
    status = tight_budget.record_retry()
    assert status.status == "hard_stop"


def test_reset_clears_counters(tight_budget: BudgetMonitor) -> None:
    tight_budget.record_tokens(100)
    tight_budget.reset()
    status = tight_budget.record_tokens(1)
    assert status.status == "ok"
    assert status.tokens_used == 1


def test_budget_status_fields_present(tight_budget: BudgetMonitor) -> None:
    status = tight_budget.check_wall_clock()
    assert hasattr(status, "tokens_used")
    assert hasattr(status, "tool_calls_used")
    assert hasattr(status, "wall_seconds_used")
    assert hasattr(status, "retries_used")
