from __future__ import annotations

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.git_metadata import capture_snapshot, collect_git_metadata


def test_clean_git_snapshot(python_basic_repo) -> None:
    metadata = collect_git_metadata(python_basic_repo, "repo:test", IndexingConfig())
    assert metadata.is_git
    assert metadata.git_sha
    assert not metadata.dirty


def test_dirty_snapshot_id_is_stable_and_changes_with_content(
    python_basic_repo,
) -> None:
    config = IndexingConfig()
    target = python_basic_repo / "src" / "pkg" / "core.py"
    target.write_text(
        target.read_text(encoding="utf-8") + "\n# dirty\n", encoding="utf-8"
    )
    first, _, meta_first = capture_snapshot("repo:test", python_basic_repo, config)
    second, _, meta_second = capture_snapshot("repo:test", python_basic_repo, config)
    assert first.dirty
    assert (
        first.worktree_snapshot_id
        == second.worktree_snapshot_id
        == meta_first.worktree_snapshot_id
        == meta_second.worktree_snapshot_id
    )
    target.write_text(
        target.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8"
    )
    third, _, _ = capture_snapshot("repo:test", python_basic_repo, config)
    assert third.worktree_snapshot_id != first.worktree_snapshot_id


def test_non_git_repo_fallback(tmp_path) -> None:
    root = tmp_path / "plain"
    root.mkdir()
    snapshot, _, metadata = capture_snapshot("repo:plain", root, IndexingConfig())
    assert not metadata.is_git
    assert snapshot.worktree_snapshot_id
