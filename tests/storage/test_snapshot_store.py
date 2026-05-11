"""Tests for the snapshot ledger."""

from __future__ import annotations

import pytest

from llm_sca_tooling.storage import WorkspaceStore
from llm_sca_tooling.storage.errors import SnapshotNotFoundError


async def test_record_clean_snapshot(workspace: WorkspaceStore, tmp_path) -> None:
    repo = await workspace.registry.register_repo(tmp_path)
    snap = await workspace.snapshots.record_snapshot(
        repo.repo_id, git_sha="abc123", branch="main", index_status="fresh"
    )
    assert snap.git_sha == "abc123"
    assert snap.dirty is False


async def test_record_dirty_snapshot(workspace: WorkspaceStore, tmp_path) -> None:
    repo = await workspace.registry.register_repo(tmp_path)
    snap = await workspace.snapshots.record_snapshot(
        repo.repo_id,
        git_sha="abc123",
        dirty=True,
        worktree_snapshot_id="wt:xyz",
        index_status="partial",
    )
    assert snap.dirty is True
    assert snap.worktree_snapshot_id == "wt:xyz"


async def test_get_snapshot_not_found(workspace: WorkspaceStore) -> None:
    with pytest.raises(SnapshotNotFoundError):
        await workspace.snapshots.get_snapshot("snap:nonexistent")


async def test_get_latest_snapshot(workspace: WorkspaceStore, tmp_path) -> None:
    repo = await workspace.registry.register_repo(tmp_path)
    await workspace.snapshots.record_snapshot(
        repo.repo_id, git_sha="aaa", index_status="stale"
    )
    await workspace.snapshots.record_snapshot(
        repo.repo_id, git_sha="bbb", index_status="fresh"
    )
    latest = await workspace.snapshots.get_latest_snapshot(repo.repo_id)
    assert latest is not None

    fresh = await workspace.snapshots.get_latest_snapshot(
        repo.repo_id, require_fresh=True
    )
    assert fresh is not None
    assert fresh.index_status == "fresh"


async def test_list_snapshots_filters_status_and_limit(
    workspace: WorkspaceStore, tmp_path
) -> None:
    repo = await workspace.registry.register_repo(tmp_path)
    await workspace.snapshots.record_snapshot(
        repo.repo_id, git_sha="aaa", index_status="stale"
    )
    await workspace.snapshots.record_snapshot(
        repo.repo_id, git_sha="bbb", index_status="fresh"
    )

    stale = await workspace.snapshots.list_snapshots(
        repo.repo_id, status="stale", limit=1
    )
    assert len(stale) == 1
    assert stale[0].index_status == "stale"


async def test_mark_snapshot_status(workspace: WorkspaceStore, tmp_path) -> None:
    repo = await workspace.registry.register_repo(tmp_path)
    snap = await workspace.snapshots.record_snapshot(repo.repo_id, git_sha="abc")
    await workspace.snapshots.mark_snapshot_status(
        snap.snapshot_id, "stale", diagnostics=[{"message": "outdated"}]
    )
    fetched = await workspace.snapshots.get_snapshot(snap.snapshot_id)
    assert fetched.index_status == "stale"


async def test_mark_snapshot_status_missing(workspace: WorkspaceStore) -> None:
    with pytest.raises(SnapshotNotFoundError):
        await workspace.snapshots.mark_snapshot_status("snap:missing", "unknown")


async def test_detect_mixed_snapshots_clean(
    workspace: WorkspaceStore, tmp_path
) -> None:
    repo = await workspace.registry.register_repo(tmp_path)
    s1 = await workspace.snapshots.record_snapshot(repo.repo_id, git_sha="aaa")
    s2 = await workspace.snapshots.record_snapshot(repo.repo_id, git_sha="aaa")
    result = await workspace.snapshots.detect_mixed_snapshots(
        [s1.snapshot_id, s2.snapshot_id]
    )
    assert result.is_mixed is False


async def test_detect_mixed_snapshots_empty(workspace: WorkspaceStore) -> None:
    result = await workspace.snapshots.detect_mixed_snapshots([])
    assert result.is_mixed is False
    assert result.snapshot_ids == []


async def test_detect_mixed_snapshots_mixed(
    workspace: WorkspaceStore, tmp_path
) -> None:
    repo = await workspace.registry.register_repo(tmp_path)
    s1 = await workspace.snapshots.record_snapshot(repo.repo_id, git_sha="aaa")
    s2 = await workspace.snapshots.record_snapshot(repo.repo_id, git_sha="bbb")
    result = await workspace.snapshots.detect_mixed_snapshots(
        [s1.snapshot_id, s2.snapshot_id]
    )
    assert result.is_mixed is True
    assert result.reason is not None


async def test_detect_mixed_clean_and_dirty_snapshots(
    workspace: WorkspaceStore, tmp_path
) -> None:
    repo = await workspace.registry.register_repo(tmp_path)
    clean = await workspace.snapshots.record_snapshot(repo.repo_id, git_sha="aaa")
    dirty = await workspace.snapshots.record_snapshot(
        repo.repo_id, dirty=True, worktree_snapshot_id="wt:aaa"
    )
    result = await workspace.snapshots.detect_mixed_snapshots(
        [clean.snapshot_id, dirty.snapshot_id]
    )
    assert result.is_mixed is True
    assert "dirty" in (result.reason or "")


async def test_detect_mixed_status_snapshot(
    workspace: WorkspaceStore, tmp_path
) -> None:
    repo = await workspace.registry.register_repo(tmp_path)
    snap = await workspace.snapshots.record_snapshot(
        repo.repo_id, git_sha="aaa", index_status="mixed"
    )
    result = await workspace.snapshots.detect_mixed_snapshots([snap.snapshot_id])
    assert result.is_mixed is True
    assert "index_status=mixed" in (result.reason or "")
