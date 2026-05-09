"""Tests for the tree-sitter indexing backend."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

from llm_sca_tooling.indexing.backends.tree_sitter import TreeSitterBackend
from llm_sca_tooling.schemas.enums import IndexStatus
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef

TS = "2026-05-09T00:00:00Z"


@pytest.fixture
def repo() -> RepoRef:
    return RepoRef(repo_id="repo:ts-test", name="ts-test")


@pytest.fixture
def snapshot(repo: RepoRef) -> SnapshotRef:
    return SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="deadbeef" * 5,
        branch="main",
        worktree_snapshot_id=None,
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )


def test_detect_capabilities_returns_valid_structure() -> None:
    backend = TreeSitterBackend()
    caps = backend.detect_capabilities()
    assert caps.backend_id == "tree-sitter"
    assert isinstance(caps.installed, bool)
    assert caps.requires_external_binary is False


def test_detect_capabilities_installed_matches_importlib() -> None:
    backend = TreeSitterBackend()
    caps = backend.detect_capabilities()
    expected = importlib.util.find_spec("tree_sitter") is not None
    assert caps.installed == expected


def test_backend_version_when_unavailable() -> None:
    backend = TreeSitterBackend()
    with patch("importlib.util.find_spec", return_value=None):
        version = backend.backend_version()
    assert version == "unavailable"


def test_backend_version_when_available() -> None:
    backend = TreeSitterBackend()
    mock_spec = object()
    with patch("importlib.util.find_spec", return_value=mock_spec):
        version = backend.backend_version()
    assert version == "available"


def test_index_files_returns_diagnostic_when_unavailable(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    backend = TreeSitterBackend()
    with patch("importlib.util.find_spec", return_value=None):
        result = backend.index_files(tmp_path, repo, snapshot, files=[])
    assert result.backend_id == "tree-sitter"
    assert any(d.code == "backend_unavailable" for d in result.diagnostics)


def test_supported_node_types_are_listed() -> None:
    backend = TreeSitterBackend()
    caps = backend.detect_capabilities()
    assert "function" in caps.supported_node_types
    assert "class" in caps.supported_node_types
