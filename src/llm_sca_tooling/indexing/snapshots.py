"""Snapshot capture — bridge between git metadata and Phase 2 snapshot ledger."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from llm_sca_tooling.indexing.git_metadata import GitMetadata, make_worktree_snapshot_id
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.snapshots import SnapshotRecord, SnapshotStore

__all__ = ["capture_snapshot"]


async def capture_snapshot(
    snapshot_store: SnapshotStore,
    repo_ref: RepoRef,
    git_meta: GitMetadata,
    repo_root: Path | None = None,
) -> tuple[SnapshotRecord, SnapshotRef]:
    """Record a snapshot in Phase 2 storage and return (storage_record, schema_ref).

    Returns both the storage :class:`SnapshotRecord` (with its generated
    ``snapshot_id``) and the Phase 1 :class:`SnapshotRef` (with ``repo_id``
    and ``git_sha``) so callers can pass either to storage writes or schema models.
    """
    from llm_sca_tooling.schemas.provenance import IndexStatus

    now = datetime.now(UTC).isoformat()
    worktree_id = (
        make_worktree_snapshot_id(
            repo_ref.repo_id,
            git_meta.git_sha,
            git_meta.changed_files + git_meta.untracked_files,
            repo_root,
        )
        if git_meta.dirty
        else None
    )

    index_status = "unknown"
    if git_meta.is_git_repo:
        index_status = "partial" if git_meta.dirty else "unknown"

    storage_record = await snapshot_store.record_snapshot(
        repo_ref.repo_id,
        git_sha=git_meta.git_sha,
        branch=git_meta.branch,
        dirty=git_meta.dirty,
        worktree_snapshot_id=worktree_id,
        index_status=index_status,
    )

    schema_ref = SnapshotRef(
        repo_id=repo_ref.repo_id,
        git_sha=git_meta.git_sha,
        branch=git_meta.branch,
        dirty=git_meta.dirty,
        worktree_snapshot_id=worktree_id,
        index_status=IndexStatus(index_status),
        captured_ts=now,
    )

    return storage_record, schema_ref
