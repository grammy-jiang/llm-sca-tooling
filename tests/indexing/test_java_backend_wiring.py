"""Java backend wiring into the indexing service (queue item 2).

JavaBackend existed but was never invoked by IndexingService — `.java` files
were silently skipped and `backend_versions` never carried a java entry.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from llm_sca_tooling.indexing.service import IndexingService
from llm_sca_tooling.storage import WorkspaceStore

JAVA_SOURCE = """\
public class UserService {
    public boolean validate(String user) {
        return user != null;
    }
}
"""


@pytest.fixture()
def java_repo(tmp_path: Path, python_basic_repo: Path) -> Path:
    repo = tmp_path / "java_repo"
    shutil.copytree(python_basic_repo, repo)
    shutil.rmtree(repo / ".git", ignore_errors=True)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "UserService.java").write_text(JAVA_SOURCE)
    git = shutil.which("git") or "git"
    subprocess.run([git, "init", "-q"], cwd=repo, check=True)  # noqa: S603
    subprocess.run([git, "add", "-A"], cwd=repo, check=True)  # noqa: S603
    subprocess.run(  # noqa: S603
        [git, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=repo,
        check=True,
    )
    return repo


async def test_java_backend_disabled_by_default(
    workspace: WorkspaceStore, java_repo: Path, monkeypatch
) -> None:
    monkeypatch.delenv("LLM_SCA_JAVA_BACKEND_ENABLED", raising=False)
    result = await IndexingService(workspace).graph_build(java_repo)
    assert "java" not in result.backend_versions


async def test_java_backend_runs_when_enabled(
    workspace: WorkspaceStore, java_repo: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_SCA_JAVA_BACKEND_ENABLED", "1")
    result = await IndexingService(workspace).graph_build(java_repo)
    assert "java" in result.backend_versions
