"""Shared fixtures for storage tests.

All storage-layer fixtures use actual registered repositories so that
repo_id values are consistent between Phase 1 schema models and Phase 2 rows.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    Provenance,
    RepoRef,
    SnapshotRef,
)
from llm_sca_tooling.storage import WorkspaceStore
from llm_sca_tooling.storage.registry import RepositoryRecord
from llm_sca_tooling.storage.snapshots import SnapshotRecord

NOW = "2026-05-09T12:00:00Z"
REPO_ID = "repo:test"


@pytest.fixture()
async def workspace(tmp_path: Path) -> WorkspaceStore:
    store = await WorkspaceStore.initialize(tmp_path, in_memory=True)
    return store


@pytest.fixture()
async def registered_repo(
    workspace: WorkspaceStore, tmp_path: Path
) -> RepositoryRecord:
    return await workspace.registry.register_repo(tmp_path, name="test-repo")


@pytest.fixture()
async def recorded_snapshot(
    workspace: WorkspaceStore, registered_repo: RepositoryRecord
) -> SnapshotRecord:
    return await workspace.snapshots.record_snapshot(
        registered_repo.repo_id,
        git_sha="abc123deadbeef",
        branch="main",
        index_status="fresh",
    )


@pytest.fixture()
def storage_repo_ref(registered_repo: RepositoryRecord) -> RepoRef:
    return RepoRef(
        repo_id=registered_repo.repo_id, name="test-repo", default_branch="main"
    )


@pytest.fixture()
def storage_snapshot_ref(
    storage_repo_ref: RepoRef, recorded_snapshot: SnapshotRecord
) -> SnapshotRef:
    return SnapshotRef(
        repo_id=storage_repo_ref.repo_id,
        git_sha=recorded_snapshot.git_sha,
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )


@pytest.fixture()
def storage_provenance(
    storage_repo_ref: RepoRef, storage_snapshot_ref: SnapshotRef
) -> Provenance:
    return Provenance(
        source_tool="tree-sitter",
        source_version="0.22",
        repo=storage_repo_ref,
        snapshot=storage_snapshot_ref,
        derivation=DerivationType.parser,
        confidence=1.0,
        evidence_strength=EvidenceStrength.hard_static,
        created_ts=NOW,
    )


@pytest.fixture()
def repo_ref() -> RepoRef:
    return RepoRef(repo_id=REPO_ID, name="test", default_branch="main")


@pytest.fixture()
def snapshot_ref() -> SnapshotRef:
    return SnapshotRef(
        repo_id=REPO_ID,
        git_sha="abc123",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )


@pytest.fixture()
def parser_provenance(repo_ref: RepoRef, snapshot_ref: SnapshotRef) -> Provenance:
    return Provenance(
        source_tool="tree-sitter",
        repo=repo_ref,
        snapshot=snapshot_ref,
        derivation=DerivationType.parser,
        confidence=1.0,
        evidence_strength=EvidenceStrength.hard_static,
        created_ts=NOW,
    )
