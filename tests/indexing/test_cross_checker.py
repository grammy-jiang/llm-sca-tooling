"""Tests for CrossChecker."""

from __future__ import annotations

import pytest

from llm_sca_tooling.indexing.backends.cross_check import (
    CrossChecker,
    EvidenceAgreement,
)
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.schemas.enums import GraphNodeType, IndexStatus
from llm_sca_tooling.schemas.graph import GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts

TS = "2026-05-09T00:00:00Z"


@pytest.fixture
def repo() -> RepoRef:
    return RepoRef(repo_id="repo:cross-test", name="cross-test")


@pytest.fixture
def snapshot(repo: RepoRef) -> SnapshotRef:
    return SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="cafebabe" * 5,
        branch="main",
        worktree_snapshot_id=None,
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )


def _make_node(
    nid: str,
    label: str,
    qualified_name: str,
    repo: RepoRef,
    snapshot: SnapshotRef,
    *,
    file_path: str = "src/a.py",
) -> GraphNode:
    prov = make_provenance(source_tool="test", repo=repo, snapshot=snapshot)
    return GraphNode(
        node_id=nid,
        node_type=GraphNodeType.FUNCTION,
        label=label,
        qualified_name=qualified_name,
        repo=repo,
        snapshot=snapshot,
        file_path=file_path,
        provenance=prov,
        properties={},
        created_ts=_now_ts(),
    )


def test_compare_single_fact_returns_candidate(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    checker = CrossChecker()
    node = _make_node("node:a:1", "func_a", "mod.func_a", repo, snapshot)
    agreement, diagnostics = checker.compare([node], ["backend_a"])

    assert isinstance(agreement, EvidenceAgreement)
    assert agreement.agreement == "candidate"
    assert agreement.contributing_backends == ["backend_a"]
    assert diagnostics == []


def test_compare_identical_facts_two_backends_returns_confirmed(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    checker = CrossChecker()
    node_a = _make_node("node:a:2", "func_b", "mod.func_b", repo, snapshot)
    node_b = _make_node("node:a:3", "func_b", "mod.func_b", repo, snapshot)
    agreement, diagnostics = checker.compare(
        [node_a, node_b], ["backend_a", "backend_b"]
    )

    assert agreement.agreement == "confirmed"
    assert "backend_a" in agreement.contributing_backends
    assert "backend_b" in agreement.contributing_backends
    assert diagnostics == []


def test_compare_divergent_facts_returns_conflicting(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    checker = CrossChecker()
    node_a = _make_node(
        "node:a:4", "func_x", "mod.func_x", repo, snapshot, file_path="src/a.py"
    )
    node_b = _make_node(
        "node:a:5", "func_y", "mod.func_y", repo, snapshot, file_path="src/b.py"
    )
    agreement, diagnostics = checker.compare(
        [node_a, node_b], ["backend_a", "backend_b"]
    )

    assert agreement.agreement == "conflicting"
    assert len(agreement.conflict_notes) > 0
    assert any(d.code == "CROSS_CHECK_CONFLICT" for d in diagnostics)


def test_agreement_has_fact_id_and_fact_type(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    checker = CrossChecker()
    node = _make_node("node:a:6", "func_z", "mod.func_z", repo, snapshot)
    agreement, _ = checker.compare([node], ["backend_x"])

    assert agreement.fact_id == node.node_id
    assert agreement.fact_type == GraphNodeType.FUNCTION.value
