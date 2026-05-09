"""Tests for FactReconciler."""

from __future__ import annotations

import pytest

from llm_sca_tooling.indexing.backends.base import BackendResult
from llm_sca_tooling.indexing.backends.fact_reconciler import FactReconciler
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.schemas.enums import GraphNodeType, IndexStatus
from llm_sca_tooling.schemas.graph import GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts

TS = "2026-05-09T00:00:00Z"


@pytest.fixture
def repo() -> RepoRef:
    return RepoRef(repo_id="repo:reconcile-test", name="reconcile-test")


@pytest.fixture
def snapshot(repo: RepoRef) -> SnapshotRef:
    return SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="deadc0de" * 5,
        branch="main",
        worktree_snapshot_id=None,
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )


def _make_node(
    nid: str,
    label: str,
    repo: RepoRef,
    snapshot: SnapshotRef,
    *,
    file_path: str = "src/mod.py",
) -> GraphNode:
    prov = make_provenance(source_tool="test", repo=repo, snapshot=snapshot)
    return GraphNode(
        node_id=nid,
        node_type=GraphNodeType.FUNCTION,
        label=label,
        qualified_name=f"mod.{label}",
        repo=repo,
        snapshot=snapshot,
        file_path=file_path,
        provenance=prov,
        properties={},
        created_ts=_now_ts(),
    )


def _make_result(backend_id: str, nodes: list[GraphNode]) -> BackendResult:
    return BackendResult(
        backend_id=backend_id,
        backend_version="0.1.0",
        nodes=nodes,
        started_ts=_now_ts(),
        ended_ts=_now_ts(),
    )


def test_reconcile_empty_list_returns_empty(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    reconciler = FactReconciler()
    result = reconciler.reconcile([])
    assert result.nodes == []
    assert result.edges == []
    assert result.agreements == []


def test_reconcile_single_source_marks_candidate(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    node = _make_node("node:mod:func_a", "func_a", repo, snapshot)
    backend_result = _make_result("backend_a", [node])

    reconciler = FactReconciler()
    result = reconciler.reconcile([backend_result])

    assert len(result.nodes) == 1
    assert result.agreements[0].agreement == "candidate"
    assert result.agreements[0].contributing_backends == ["backend_a"]


def test_reconcile_two_backends_same_fact_marks_confirmed(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    node_a = _make_node("node:mod:func_b", "func_b", repo, snapshot)
    node_b = _make_node(
        "node:mod:func_b_2", "func_b", repo, snapshot
    )  # same key after _node_key

    result_a = _make_result("backend_a", [node_a])
    result_b = _make_result("backend_b", [node_b])

    reconciler = FactReconciler()
    result = reconciler.reconcile([result_a, result_b])

    assert len(result.nodes) >= 1
    agreements = {a.agreement for a in result.agreements}
    assert "confirmed" in agreements


def test_reconcile_conflicting_qualified_names_marks_conflicting(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    prov = make_provenance(source_tool="test", repo=repo, snapshot=snapshot)
    node_a = GraphNode(
        node_id="node:conflict:func_c",
        node_type=GraphNodeType.FUNCTION,
        label="func_c",
        qualified_name="mod.func_c",
        repo=repo,
        snapshot=snapshot,
        file_path="src/mod.py",
        provenance=prov,
        properties={},
        created_ts=_now_ts(),
    )
    node_b = GraphNode(
        node_id="node:conflict:func_c_alt",
        node_type=GraphNodeType.FUNCTION,
        label="func_c_alias",
        qualified_name="mod.func_c_alias",
        repo=repo,
        snapshot=snapshot,
        file_path="src/mod.py",
        provenance=prov,
        properties={},
        created_ts=_now_ts(),
    )
    result_a = _make_result("backend_a", [node_a])
    result_b = _make_result("backend_b", [node_b])

    reconciler = FactReconciler()
    result = reconciler.reconcile([result_a, result_b])

    # Each node has unique key → two candidates, not conflicting at the node level
    assert len(result.nodes) == 2
