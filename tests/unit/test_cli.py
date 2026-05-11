"""Tests for the CLI commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import llm_sca_tooling.cli.main as cli_main
from llm_sca_tooling.cli.main import app
from llm_sca_tooling.errors import ConfigError

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "llm-sca-tooling" in result.output


def test_help_output() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "config" in result.output


def test_config_show_exits_zero() -> None:
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0


def test_config_validate_valid_config() -> None:
    result = runner.invoke(app, ["config", "validate"])
    assert result.exit_code == 0


def test_config_validate_invalid_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"policy": {"permission_profile": "superuser"}}')
    result = runner.invoke(app, ["config", "validate", str(bad)])
    assert result.exit_code != 0


def test_run_create_exits_zero() -> None:
    result = runner.invoke(app, ["run", "create", "test-workflow"])
    assert result.exit_code == 0
    assert "run:" in result.output


def test_config_show_with_bad_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_bytes(b"\xff\xfe invalid toml")
    result = runner.invoke(app, ["config", "show", "--config", str(bad)])
    assert result.exit_code != 0


def test_config_show_handles_config_error(monkeypatch) -> None:
    def raise_config_error(_config_file) -> None:
        raise ConfigError("bad config")

    monkeypatch.setattr(cli_main, "load_config", raise_config_error)
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 1
    assert "bad config" in result.output


def test_main_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "config" in result.output or result.exit_code == 0


def test_harness_status_runs() -> None:
    result = runner.invoke(app, ["harness", "status"])
    assert result.exit_code in (0, 2)


def test_harness_status_success(monkeypatch) -> None:
    import subprocess

    completed = subprocess.CompletedProcess(
        args=["local-agent-harness"],
        returncode=0,
        stdout='{"stage":"S2","total":20,"axes":{"governance":4}}',
        stderr="",
    )
    monkeypatch.setattr(subprocess, "run", lambda *_, **__: completed)
    result = runner.invoke(app, ["harness", "status"])
    assert result.exit_code == 0
    assert "S2" in result.output


def test_harness_status_exception(monkeypatch) -> None:
    import subprocess

    def raise_runtime_error(*_args, **_kwargs) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "run", raise_runtime_error)
    result = runner.invoke(app, ["harness", "status"])
    assert result.exit_code == 2
    assert "boom" in result.output


def test_run_create_reports_writer_error(monkeypatch) -> None:
    from llm_sca_tooling.operations.run_records import RunRecordWriter

    async def raise_runtime_error(self, workflow, repos=None):
        raise RuntimeError(f"cannot create {workflow}")

    monkeypatch.setattr(RunRecordWriter, "create_run", raise_runtime_error)
    result = runner.invoke(app, ["run", "create", "bad-workflow"])
    assert result.exit_code == 1
    assert "cannot create bad-workflow" in result.output


def test_mcp_start_invokes_server(monkeypatch) -> None:
    from llm_sca_tooling.mcp_server.server import MCPServer

    calls = []

    def fake_start(self) -> None:
        calls.append((self._config.host, self._config.port))

    monkeypatch.setattr(MCPServer, "start", fake_start)
    result = runner.invoke(
        app, ["mcp", "start", "--host", "127.0.0.1", "--port", "9998"]
    )
    assert result.exit_code == 0
    assert calls == [("127.0.0.1", 9998)]


def test_mcp_start_reports_server_error(monkeypatch) -> None:
    from llm_sca_tooling.mcp_server.server import MCPServer

    def fake_start(self) -> None:
        raise RuntimeError("server failed")

    monkeypatch.setattr(MCPServer, "start", fake_start)
    result = runner.invoke(app, ["mcp", "start"])
    assert result.exit_code == 1


def test_log_level_option() -> None:
    result = runner.invoke(app, ["--log-level", "DEBUG", "--version"])
    assert "llm-sca-tooling" in result.output
