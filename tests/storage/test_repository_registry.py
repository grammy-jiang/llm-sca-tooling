"""Tests for the repository registry."""

from __future__ import annotations

import pytest

from llm_sca_tooling.storage import WorkspaceStore
from llm_sca_tooling.storage.errors import RepositoryNotFoundError


async def test_register_repo_stores_metadata(
    workspace: WorkspaceStore, tmp_path
) -> None:
    record = await workspace.registry.register_repo(tmp_path, name="my-repo")
    assert record.name == "my-repo"
    assert record.active is True
    assert record.index_status == "not_indexed"
    assert record.root_path_hash  # non-empty


async def test_register_repo_idempotent(workspace: WorkspaceStore, tmp_path) -> None:
    r1 = await workspace.registry.register_repo(tmp_path)
    r2 = await workspace.registry.register_repo(tmp_path)
    assert r1.repo_id == r2.repo_id


async def test_list_repos_returns_registered(
    workspace: WorkspaceStore, tmp_path
) -> None:
    await workspace.registry.register_repo(tmp_path)
    repos = await workspace.registry.list_repos()
    assert any(r.root_path == tmp_path.resolve() for r in repos)


async def test_get_repo_by_id(workspace: WorkspaceStore, tmp_path) -> None:
    record = await workspace.registry.register_repo(tmp_path)
    fetched = await workspace.registry.get_repo(record.repo_id)
    assert fetched.repo_id == record.repo_id


async def test_get_repo_not_found(workspace: WorkspaceStore) -> None:
    with pytest.raises(RepositoryNotFoundError):
        await workspace.registry.get_repo("repo:nonexistent")


async def test_unregister_keeps_evidence(workspace: WorkspaceStore, tmp_path) -> None:
    record = await workspace.registry.register_repo(tmp_path)
    await workspace.registry.unregister_repo(record.repo_id, keep_evidence=True)
    active_repos = await workspace.registry.list_repos(active_only=True)
    assert not any(r.repo_id == record.repo_id for r in active_repos)
    # Should still be findable
    all_repos = await workspace.registry.list_repos(active_only=False)
    assert any(r.repo_id == record.repo_id for r in all_repos)


async def test_set_latest_snapshot(workspace: WorkspaceStore, tmp_path) -> None:
    record = await workspace.registry.register_repo(tmp_path)
    await workspace.registry.set_latest_snapshot(record.repo_id, "snap:abc")
    fetched = await workspace.registry.get_repo(record.repo_id)
    assert fetched.latest_snapshot_id == "snap:abc"


async def test_redacted_hides_root_path(workspace: WorkspaceStore, tmp_path) -> None:
    record = await workspace.registry.register_repo(tmp_path)
    redacted = record.redacted()
    assert "root_path" not in redacted
    assert redacted["root_path_hash"]
