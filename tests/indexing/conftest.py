from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from llm_sca_tooling.storage import initialize_workspace


@pytest.fixture
def python_basic_repo(tmp_path: Path) -> Path:
    root = tmp_path / "python_basic"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "pkg" / "helpers.py").write_text(
        "def helper(x):\n    return x + 1\n", encoding="utf-8"
    )
    (root / "src" / "pkg" / "core.py").write_text(
        "from pkg.helpers import helper\n\nclass Greeter:\n    def greet(self, name):\n        return helper(len(name))\n\ndef local_value(value):\n    return helper(value)\n\ndef parse_config(value):\n    return local_value(value)\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_core.py").write_text(
        "from pkg.core import parse_config\n\ndef test_parse_config():\n    assert parse_config(1) == 2\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths=['tests']\n", encoding="utf-8"
    )
    (root / ".github" / "workflows" / "ci.yml").write_text(
        "name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps: []\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test",
            "commit",
            "-m",
            "init",
        ],
        cwd=root,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return root


@pytest.fixture
def indexing_workspace(tmp_path: Path):
    store = initialize_workspace(tmp_path / "store")
    yield store
    store.close()
