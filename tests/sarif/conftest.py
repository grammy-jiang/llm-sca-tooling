from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def sarif_fixtures() -> Path:
    return Path(__file__).parent / "fixtures" / "sarif_runs"


@pytest.fixture
def indexed_repo(tmp_path: Path):
    from llm_sca_tooling.indexing.service import graph_build

    root = tmp_path / "repo"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "pkg" / "core.py").write_text(
        "def callee(x):\n    return x + 1\n\ndef caller(x):\n    return callee(x)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    workspace_path = tmp_path / "workspace"
    result = graph_build(root, workspace_path=workspace_path)
    return root, workspace_path, result

