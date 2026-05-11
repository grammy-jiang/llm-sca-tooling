"""Shared pytest fixtures for llm-sca-tooling tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.config import BudgetConfig, Config, TelemetryConfig
from llm_sca_tooling.operations.budget import BudgetMonitor
from llm_sca_tooling.operations.run_records import RunRecordWriter


@pytest.fixture()
def config(tmp_path: Path) -> Config:
    """A Config with temporary directories for test isolation."""
    return Config(
        workspace_root=tmp_path,
        telemetry=TelemetryConfig(trace_dir=tmp_path / "traces", enabled=True),
        budget=BudgetConfig(
            max_tokens=1000,
            max_tool_calls=10,
            max_retries=2,
            max_wall_seconds=60,
        ),
    )


@pytest.fixture()
def run_record_writer(tmp_path: Path) -> RunRecordWriter:
    """A RunRecordWriter backed by a temporary directory."""
    return RunRecordWriter(base_dir=tmp_path / "runs")


@pytest.fixture()
def budget_monitor(config: Config) -> BudgetMonitor:
    """A BudgetMonitor with tight limits for testing hard-stop behaviour."""
    return BudgetMonitor(config.budget)


@pytest.fixture()
def tiny_python_repo() -> Path:
    """Path to the tiny-python fixture repository."""
    return Path(__file__).parent.parent / "fixtures" / "repos" / "tiny-python"
