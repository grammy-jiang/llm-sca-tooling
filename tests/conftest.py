from __future__ import annotations

import os
from pathlib import Path

import pytest

from llm_sca_tooling.config import Config, TelemetryConfig
from llm_sca_tooling.operations.budget import BudgetMonitor
from llm_sca_tooling.operations.run_records import RunRecordWriter

os.environ.setdefault("GIT_CONFIG_COUNT", "1")
os.environ.setdefault("GIT_CONFIG_KEY_0", "commit.gpgsign")
os.environ.setdefault("GIT_CONFIG_VALUE_0", "false")


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        workspace_root=tmp_path,
        telemetry=TelemetryConfig(trace_dir=tmp_path / "traces"),
    )


@pytest.fixture
def run_record_writer(tmp_path: Path) -> RunRecordWriter:
    return RunRecordWriter(tmp_path / "runs")


@pytest.fixture
def budget_monitor() -> BudgetMonitor:
    return BudgetMonitor(
        tokens_limit=10, tool_calls_limit=2, retries_limit=1, wall_seconds_limit=60
    )


@pytest.fixture
def tiny_python_repo() -> Path:
    return Path("fixtures/repos/tiny-python")
