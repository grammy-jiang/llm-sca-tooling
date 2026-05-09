from __future__ import annotations

from llm_sca_tooling.schemas.enums import IndexStatus, SnapshotConsistency


def test_clean_and_dirty_snapshots_are_stored(
    workspace, snapshot, dirty_snapshot
) -> None:
    clean = workspace.snapshots.record_snapshot(snapshot)
    dirty = workspace.snapshots.record_snapshot(dirty_snapshot)
    assert clean.snapshot.git_sha
    assert dirty.snapshot.dirty
    assert dirty.snapshot.worktree_snapshot_id == "dirty:1"


def test_snapshot_status_and_diagnostics_round_trip(workspace, snapshot) -> None:
    record = workspace.snapshots.record_snapshot(
        snapshot, diagnostics=[{"code": "partial"}]
    )
    workspace.snapshots.mark_snapshot_status(
        record.snapshot_id, IndexStatus.STALE, diagnostics=[{"code": "stale"}]
    )
    updated = workspace.snapshots.get_snapshot(record.snapshot_id)
    assert updated.snapshot.index_status == IndexStatus.STALE
    assert updated.diagnostics[0]["code"] == "stale"


def test_latest_and_mixed_snapshot_detection(
    workspace, snapshot, dirty_snapshot
) -> None:
    clean = workspace.snapshots.record_snapshot(snapshot)
    dirty = workspace.snapshots.record_snapshot(dirty_snapshot)
    latest = workspace.snapshots.get_latest_snapshot(snapshot.repo_id)
    assert latest is not None
    mix = workspace.snapshots.detect_mixed_snapshots(
        [clean.snapshot_id, dirty.snapshot_id]
    )
    assert mix.mixed
    assert mix.snapshot_consistency == SnapshotConsistency.MIXED
