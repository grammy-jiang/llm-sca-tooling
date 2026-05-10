from __future__ import annotations

import tomllib
from pathlib import Path

from typer.testing import CliRunner

from llm_sca_tooling.cli.main import app


def test_pyproject_exposes_distribution_entrypoints() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]
    assert scripts["evidence-sca"] == "llm_sca_tooling.cli.main:app"
    assert data["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "evidence-sca" in result.output
