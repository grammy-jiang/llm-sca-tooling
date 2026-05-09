from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from llm_sca_tooling.mcp_server import CodeIntelligenceServer, McpServerConfig


@pytest.fixture
def mcp_repo(tmp_path: Path) -> Path:
    root = tmp_path / "fixture_repo"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "pkg" / "core.py").write_text(
        "def callee(x):\n    return x + 1\n\ndef caller(x):\n    return callee(x)\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_core.py").write_text(
        "from pkg.core import caller\n\ndef test_caller():\n    assert caller(1) == 2\n",
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
def mcp_server(tmp_path: Path):
    server = CodeIntelligenceServer(
        McpServerConfig.for_workspace(tmp_path / "workspace")
    ).start()
    yield server
    server.shutdown()
