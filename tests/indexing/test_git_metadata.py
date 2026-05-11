"""Tests for git metadata and dirty snapshot IDs."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing import git_metadata as git_mod
from llm_sca_tooling.indexing.git_metadata import (
    GitMetadataCollector,
    make_worktree_snapshot_id,
)


async def test_collect_non_git_repo(monkeypatch, tmp_path: Path) -> None:
    async def fake_run_git(args: list[str], cwd: Path) -> tuple[str, str, int]:
        return "", "not a git repo", 1

    monkeypatch.setattr(git_mod, "_run_git", fake_run_git)
    meta = await GitMetadataCollector().collect(tmp_path)
    assert meta.is_git_repo is False
    assert meta.diagnostics[0].code == "GIT_NOT_AVAILABLE"


async def test_collect_git_exec_error(monkeypatch, tmp_path: Path) -> None:
    async def fake_run_git(args: list[str], cwd: Path) -> tuple[str, str, int]:
        raise OSError("git missing")

    monkeypatch.setattr(git_mod, "_run_git", fake_run_git)
    meta = await GitMetadataCollector().collect(tmp_path)
    assert meta.is_git_repo is False
    assert meta.diagnostics[0].code == "GIT_EXEC_ERROR"


async def test_collect_dirty_status(monkeypatch, tmp_path: Path) -> None:
    async def fake_run_git(args: list[str], cwd: Path) -> tuple[str, str, int]:
        if args == ["rev-parse", "--is-inside-work-tree"]:
            return "true", "", 0
        if args == ["rev-parse", "HEAD"]:
            return "abc123", "", 0
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return "main", "", 0
        if args == ["status", "--porcelain=v1"]:
            return " M src/app.py\n?? scratch.py", "", 0
        return "", "", 0

    monkeypatch.setattr(git_mod, "_run_git", fake_run_git)
    meta = await GitMetadataCollector().collect(tmp_path)
    assert meta.is_git_repo is True
    assert meta.dirty is True
    assert meta.changed_files == ["src/app.py"]
    assert meta.untracked_files == ["scratch.py"]


async def test_get_changed_files_handles_diff_failure(
    monkeypatch, tmp_path: Path
) -> None:
    async def fake_run_git(args: list[str], cwd: Path) -> tuple[str, str, int]:
        return "", "bad base", 1

    monkeypatch.setattr(git_mod, "_run_git", fake_run_git)
    assert await GitMetadataCollector().get_changed_files(tmp_path, "bad") == []


async def test_get_changed_files_returns_paths(monkeypatch, tmp_path: Path) -> None:
    async def fake_run_git(args: list[str], cwd: Path) -> tuple[str, str, int]:
        return "src/app.py\n tests/test_app.py\n", "", 0

    monkeypatch.setattr(git_mod, "_run_git", fake_run_git)
    assert await GitMetadataCollector().get_changed_files(tmp_path, "base") == [
        "src/app.py",
        "tests/test_app.py",
    ]


def test_worktree_snapshot_id_includes_file_content(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    path.write_text("x = 1\n")
    first = make_worktree_snapshot_id("repo:1", "abc", ["app.py"], tmp_path)
    second = make_worktree_snapshot_id("repo:1", "abc", ["app.py"], tmp_path)
    path.write_text("x = 2\n")
    third = make_worktree_snapshot_id("repo:1", "abc", ["app.py"], tmp_path)
    assert first == second
    assert third != first


def test_worktree_snapshot_id_marks_missing_files(tmp_path: Path) -> None:
    snap = make_worktree_snapshot_id("repo:1", "abc", ["deleted.py"], tmp_path)
    assert snap.startswith("snap:repo:1:dirty:")
