"""Tests for WorkflowConfig."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.workflows.bug_resolve.config import (
    DEFAULT_WORKFLOW_CONFIG,
    WorkflowConfig,
)


def test_default_config_values() -> None:
    c = WorkflowConfig()
    assert c.max_candidates == 3
    assert c.max_repair_loops == 5
    assert c.context_budget == 8000
    assert c.token_budget == 120_000
    assert c.wall_clock_budget_seconds == 3600
    assert c.null_mode is False
    assert c.require_sarif_gate is True


def test_default_singleton_matches_defaults() -> None:
    assert DEFAULT_WORKFLOW_CONFIG == WorkflowConfig()


def test_max_candidates_bounds() -> None:
    with pytest.raises(ValidationError):
        WorkflowConfig(max_candidates=0)
    with pytest.raises(ValidationError):
        WorkflowConfig(max_candidates=21)


def test_max_repair_loops_bounds() -> None:
    with pytest.raises(ValidationError):
        WorkflowConfig(max_repair_loops=0)
    with pytest.raises(ValidationError):
        WorkflowConfig(max_repair_loops=51)


def test_context_budget_positive() -> None:
    with pytest.raises(ValidationError):
        WorkflowConfig(context_budget=0)


def test_token_budget_positive() -> None:
    with pytest.raises(ValidationError):
        WorkflowConfig(token_budget=0)


def test_wall_clock_budget_positive() -> None:
    with pytest.raises(ValidationError):
        WorkflowConfig(wall_clock_budget_seconds=0)


def test_null_mode_can_be_set() -> None:
    c = WorkflowConfig(null_mode=True)
    assert c.null_mode is True
