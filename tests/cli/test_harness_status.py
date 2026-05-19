"""CLI tests for ``llm-sca-tooling harness status``.

Regression for the graceful-degradation path: when the optional
``local-agent-harness`` binary is missing (CI, fresh checkouts, downstream
consumers), the command must warn and exit 0 — not crash with
``FileNotFoundError`` and exit code 2.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from llm_sca_tooling.cli.main import app

runner = CliRunner()


def test_harness_status_when_companion_tool_missing() -> None:
    """A missing ``local-agent-harness`` binary must not crash the CLI."""
    with patch("subprocess.run", side_effect=FileNotFoundError(2, "No such file")):
        result = runner.invoke(app, ["harness", "status"])
    assert result.exit_code == 0, result.output
    assert "not installed" in result.output.lower()


def test_harness_status_when_companion_tool_returns_error() -> None:
    """A non-zero exit from the companion tool must also degrade gracefully."""
    mock_completed: Any = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="boom"
    )
    with patch("subprocess.run", return_value=mock_completed):
        result = runner.invoke(app, ["harness", "status"])
    assert result.exit_code == 0, result.output
    assert "not available" in result.output.lower()


def test_harness_status_when_companion_tool_returns_data() -> None:
    """A 0-exit, JSON-shaped stdout must render a status table."""
    payload = {"stage": "S3", "total": 22, "axes": {"docs": 4, "security": 5}}
    mock_completed: Any = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=json.dumps(payload), stderr=""
    )
    with patch("subprocess.run", return_value=mock_completed):
        result = runner.invoke(app, ["harness", "status"])
    assert result.exit_code == 0, result.output
    assert "S3" in result.output
    assert "22" in result.output
