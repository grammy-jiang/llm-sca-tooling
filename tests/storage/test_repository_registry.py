from __future__ import annotations

import pytest

from llm_sca_tooling.storage.errors import DuplicateRepositoryError


def test_register_repo_stores_metadata(workspace, repo_root) -> None:
    repo = workspace.repositories.register_repo(repo_root, name="demo")
    assert repo.repo_id.startswith("repo:demo:")
    assert repo.root_path_hash
    assert "root_path" not in repo.public_metadata()


def test_duplicate_registration_is_idempotent(workspace, repo_root) -> None:
    first = workspace.repositories.register_repo(repo_root, name="demo")
    second = workspace.repositories.register_repo(repo_root, name="demo")
    assert second.repo_id == first.repo_id


def test_ambiguous_name_requires_id_lookup(workspace, tmp_path) -> None:
    one = tmp_path / "one"
    two = tmp_path / "two"
    one.mkdir()
    two.mkdir()
    repo_one = workspace.repositories.register_repo(one, name="same")
    repo_two = workspace.repositories.register_repo(two, name="same")
    with pytest.raises(DuplicateRepositoryError):
        workspace.repositories.get_repo("same")
    assert workspace.repositories.get_repo(repo_one.repo_id).root_path != workspace.repositories.get_repo(repo_two.repo_id).root_path


def test_unregister_keeps_evidence_and_latest_snapshot(workspace, registered_repo, snapshot) -> None:
    record = workspace.snapshots.record_snapshot(snapshot)
    workspace.repositories.set_latest_snapshot(registered_repo.repo_id, record.snapshot_id)
    inactive = workspace.repositories.unregister_repo(registered_repo.repo_id, keep_evidence=True)
    assert not inactive.active
    assert workspace.repositories.get_repo(registered_repo.repo_id).latest_snapshot_id == record.snapshot_id
