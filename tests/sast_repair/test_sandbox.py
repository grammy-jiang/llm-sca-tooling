"""Tests for the sandbox manager."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.sast_repair.models import SASTPatch
from llm_sca_tooling.sast_repair.sandbox import SandboxManager


def _make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "example.py").write_text("line1\nline2\nline3\n", encoding="utf-8")
    return repo


def test_sandbox_apply_empty_patch(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    manager = SandboxManager(sandbox_root=tmp_path / "sb")
    patch = SASTPatch(alert_id="a1")
    result = manager.apply_patch(repo_root=repo, patch=patch)
    assert result.patch_applied is True
    assert result.sandbox_snapshot_id
    diagnostics = manager.cleanup()
    assert diagnostics == []


def test_sandbox_missing_repo(tmp_path: Path) -> None:
    manager = SandboxManager(sandbox_root=tmp_path / "sb")
    patch = SASTPatch(alert_id="a1")
    result = manager.apply_patch(repo_root=tmp_path / "missing", patch=patch)
    assert result.patch_applied is False
    assert result.apply_error and "does not exist" in result.apply_error


def test_sandbox_apply_unified_diff(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    manager = SandboxManager(sandbox_root=tmp_path / "sb")
    diff_text = (
        "--- a/src/example.py\n"
        "+++ b/src/example.py\n"
        "@@ -1,3 +1,3 @@\n"
        "+inserted\n"
        "-line1\n"
        " line2\n"
        " line3\n"
    )
    patch = SASTPatch(
        alert_id="a1", diff_text=diff_text, changed_files=["src/example.py"]
    )
    result = manager.apply_patch(repo_root=repo, patch=patch)
    assert result.patch_applied is True
    sandboxed = Path(result.sandbox_path) / "src" / "example.py"
    assert "inserted" in sandboxed.read_text(encoding="utf-8")
    manager.cleanup()


def test_sandbox_apply_diff_missing_target(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    manager = SandboxManager(sandbox_root=tmp_path / "sb")
    diff_text = (
        "--- a/src/missing.py\n" "+++ b/src/missing.py\n" "@@ -1,1 +1,1 @@\n" "+x\n"
    )
    patch = SASTPatch(
        alert_id="a1", diff_text=diff_text, changed_files=["src/missing.py"]
    )
    result = manager.apply_patch(repo_root=repo, patch=patch)
    assert result.patch_applied is False
    assert result.apply_error and "apply_failed" in result.apply_error
    manager.cleanup()


def test_sandbox_default_root_creates_dir() -> None:
    manager = SandboxManager()
    assert manager.sandbox_root.exists()
    manager.cleanup()
