"""Tests for workspace initialization and migration."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.storage import WorkspaceStore
from llm_sca_tooling.storage.errors import WorkspaceNotFoundError


async def test_initialize_creates_workspace(tmp_path: Path) -> None:
    store = await WorkspaceStore.initialize(tmp_path)
    async with store:
        status = await store.status()
        assert status.is_open is True
    assert store._closed is True  # context manager closed it
    assert "0001" in status.applied_migrations


async def test_initialize_in_memory() -> None:
    store = await WorkspaceStore.initialize(Path(), in_memory=True)
    async with store:
        status = await store.status()
    assert status.workspace_id != ""


async def test_workspace_status_fields(workspace: WorkspaceStore) -> None:
    status = await workspace.status()
    assert status.workspace_id
    assert "0001" in status.applied_migrations


async def test_initialize_idempotent(tmp_path: Path) -> None:
    """Opening the same workspace twice should not fail."""
    s1 = await WorkspaceStore.initialize(tmp_path)
    await s1.close()
    s2 = await WorkspaceStore.initialize(tmp_path)
    async with s2:
        status = await s2.status()
    assert "0001" in status.applied_migrations


async def test_open_existing_workspace(tmp_path: Path) -> None:
    first = await WorkspaceStore.initialize(tmp_path)
    original_status = await first.status()
    await first.close()

    opened = await WorkspaceStore.open(tmp_path)
    async with opened:
        status = await opened.status()
    assert status.workspace_id == original_status.workspace_id
    assert status.is_open is True


async def test_open_missing_workspace_fails(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceNotFoundError):
        await WorkspaceStore.open(tmp_path)


async def test_close_is_idempotent(workspace: WorkspaceStore) -> None:
    await workspace.close()
    await workspace.close()
    status = await workspace.status()
    assert status.is_open is False


async def test_migration_applied_once(workspace: WorkspaceStore) -> None:
    """Applying migrations twice should not duplicate entries."""
    from llm_sca_tooling.storage.migrations import MigrationManager

    async with workspace._session_factory() as session:
        manager = MigrationManager(session)
        new_applied = await manager.apply_pending()
    assert new_applied == []


async def test_checksum_verification_passes(workspace: WorkspaceStore) -> None:
    from llm_sca_tooling.storage.migrations import MigrationManager

    async with workspace._session_factory() as session:
        manager = MigrationManager(session)
        await manager.verify_checksums()
