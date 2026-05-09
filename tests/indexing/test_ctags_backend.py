"""Tests for the ctags indexing backend."""

from __future__ import annotations

import shutil

import pytest

from llm_sca_tooling.indexing.backends.ctags import CtagsBackend, parse_ctags_json_lines
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.scanner import node_id
from llm_sca_tooling.schemas.enums import GraphNodeType, IndexStatus
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef

TS = "2026-05-09T00:00:00Z"


@pytest.fixture
def repo() -> RepoRef:
    return RepoRef(repo_id="repo:ctags-test", name="ctags-test")


@pytest.fixture
def snapshot(repo: RepoRef) -> SnapshotRef:
    return SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="abc123" * 7,
        branch="main",
        worktree_snapshot_id=None,
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )


def test_detect_capabilities_returns_valid_structure() -> None:
    backend = CtagsBackend()
    caps = backend.detect_capabilities()
    assert caps.backend_id == "ctags"
    assert isinstance(caps.installed, bool)
    assert caps.requires_external_binary is True


def test_detect_capabilities_installed_matches_which() -> None:
    backend = CtagsBackend()
    caps = backend.detect_capabilities()
    has_binary = bool(shutil.which("ctags") or shutil.which("universal-ctags"))
    assert caps.installed == has_binary


@pytest.mark.skipif(
    not (shutil.which("ctags") or shutil.which("universal-ctags")),
    reason="ctags not installed",
)
def test_backend_version_non_empty_when_installed() -> None:
    backend = CtagsBackend()
    version = backend.backend_version()
    assert version not in ("unavailable", "")


def _make_module_node(repo: RepoRef, snapshot: SnapshotRef) -> object:
    from llm_sca_tooling.schemas.graph import GraphNode
    from llm_sca_tooling.storage.workspace import _now_ts

    provenance = make_provenance(source_tool="ctags", repo=repo, snapshot=snapshot)
    return GraphNode(
        node_id=node_id(repo.repo_id, snapshot, GraphNodeType.MODULE, "module:test"),
        node_type=GraphNodeType.MODULE,
        label="test_module",
        qualified_name="test_module",
        repo=repo,
        snapshot=snapshot,
        file_path="test_module.py",
        provenance=provenance,
        properties={},
        created_ts=_now_ts(),
    )


def test_parse_ctags_json_lines_produces_function_and_class_nodes(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    module_node = _make_module_node(repo, snapshot)
    lines = [
        '{"name": "MyClass", "kind": "class", "line": 5}',
        '{"name": "my_func", "kind": "function", "line": 10}',
    ]
    result = parse_ctags_json_lines(
        lines, repo, snapshot, module_node, "test_module.py"
    )
    assert len(result.nodes) == 2
    types = {node.node_type for node in result.nodes}
    assert GraphNodeType.CLASS in types
    assert GraphNodeType.FUNCTION in types


def test_parse_ctags_json_lines_skips_invalid_json(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    module_node = _make_module_node(repo, snapshot)
    lines = ["not-json", '{"name": "good_func", "kind": "function", "line": 1}']
    result = parse_ctags_json_lines(
        lines, repo, snapshot, module_node, "test_module.py"
    )
    assert len(result.nodes) == 1
    assert result.diagnostics  # bad JSON line → diagnostic


def test_parse_ctags_json_lines_skips_entries_with_no_name(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    module_node = _make_module_node(repo, snapshot)
    lines = ['{"kind": "function", "line": 3}']
    result = parse_ctags_json_lines(
        lines, repo, snapshot, module_node, "test_module.py"
    )
    assert result.nodes == []


def test_parse_ctags_json_lines_produces_contains_edges(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    module_node = _make_module_node(repo, snapshot)
    lines = ['{"name": "helper", "kind": "function", "line": 2}']
    result = parse_ctags_json_lines(
        lines, repo, snapshot, module_node, "test_module.py"
    )
    assert len(result.edges) == 1
    assert result.edges[0].source_id == module_node.node_id
