from __future__ import annotations

import tomllib
from pathlib import Path

from llm_sca_tooling.cli.indexing import main as evidence_sca_main


def test_pyproject_exposes_distribution_entrypoints(capsys) -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]
    assert scripts["evidence-sca"] == "llm_sca_tooling.cli.indexing:main"
    assert scripts["llm-sca-tooling"] == "llm_sca_tooling.cli.main:app"
    assert data["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    assert evidence_sca_main(["--version"]) == 0
    assert "evidence-sca" in capsys.readouterr().out
