from __future__ import annotations

from typer.testing import CliRunner

from llm_sca_tooling.cli.main import app


def test_cli_version_option() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "llm-sca-tooling" in result.output


def test_cli_config_show() -> None:
    result = CliRunner().invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "llm-sca-tooling" in result.output


def test_cli_run_create(tmp_path) -> None:
    result = CliRunner().invoke(
        app, ["run", "create", "demo", "--run-dir", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert result.output.startswith("run:")
