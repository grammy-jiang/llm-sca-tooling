"""Tests for GraphManifestGenerator."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.indexing.manifests import GraphManifestGenerator
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.schemas.enums import (
    GraphEdgeType,
    GraphNodeType,
    IndexStatus,
)
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage import initialize_workspace
from llm_sca_tooling.storage.workspace import _now_ts

TS = "2026-05-09T00:00:00Z"
SNAPSHOT_ID = "snap:abc123"


@pytest.fixture
def workspace(tmp_path: Path):
    store = initialize_workspace(tmp_path / ".llm-sca")
    yield store
    store.close()


@pytest.fixture
def repo(workspace, tmp_path: Path) -> RepoRef:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    registered = workspace.repositories.register_repo(repo_root, name="manifest-test")
    return RepoRef(repo_id=registered.repo_id, name=registered.name)


@pytest.fixture
def snapshot(workspace, repo: RepoRef) -> SnapshotRef:
    snap = SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="abc123ef" * 5,
        branch="main",
        worktree_snapshot_id=None,
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )
    workspace.snapshots.record_snapshot(snap)
    return snap


@pytest.fixture
def snapshot_id(workspace, repo: RepoRef, snapshot: SnapshotRef) -> str:
    from llm_sca_tooling.storage.ids import snapshot_id_for

    return snapshot_id_for(snapshot)


@pytest.fixture
def run_id(workspace, repo: RepoRef) -> str:
    rid = "run:manifest-test"
    workspace.conn.execute(
        """INSERT OR IGNORE INTO run_records
           (run_id, workflow, user_intent_hash, status, start_ts, toolset_hash,
            policy_id, permission_profile, run_event_count, redaction_policy_json,
            payload_json, created_ts, updated_ts)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rid,
            "graph-build",
            "hash:intent",
            "running",
            TS,
            "hash:tools",
            "policy:default",
            "default",
            0,
            '{"policy_id":"p","default_status":"redacted"}',
            "{}",
            TS,
            TS,
        ),
    )
    workspace.conn.execute(
        "INSERT OR IGNORE INTO run_repositories(run_id, repo_id) VALUES (?, ?)",
        (rid, repo.repo_id),
    )
    workspace.conn.commit()
    return rid


def _make_node(idx: int, repo: RepoRef, snapshot: SnapshotRef) -> GraphNode:
    provenance = make_provenance(source_tool="test", repo=repo, snapshot=snapshot)
    return GraphNode(
        node_id=f"node:test:{idx}",
        node_type=GraphNodeType.FUNCTION,
        label=f"func_{idx}",
        qualified_name=f"mod.func_{idx}",
        repo=repo,
        snapshot=snapshot,
        file_path="mod.py",
        provenance=provenance,
        properties={},
        created_ts=_now_ts(),
    )


def _make_edge(
    src: GraphNode, tgt: GraphNode, repo: RepoRef, snapshot: SnapshotRef
) -> GraphEdge:
    provenance = make_provenance(source_tool="test", repo=repo, snapshot=snapshot)
    return GraphEdge(
        edge_id=f"edge:{src.node_id}:{tgt.node_id}",
        edge_type=GraphEdgeType.CALLS,
        source_id=src.node_id,
        target_id=tgt.node_id,
        repo=repo,
        snapshot=snapshot,
        provenance=provenance,
        confidence=1.0,
        properties={},
        created_ts=_now_ts(),
    )


def test_manifest_generate_writes_chunk_files(
    workspace,
    repo: RepoRef,
    snapshot: SnapshotRef,
    snapshot_id: str,
    run_id: str,
    tmp_path: Path,
) -> None:
    node_a = _make_node(0, repo, snapshot)
    node_b = _make_node(1, repo, snapshot)
    workspace.graph.upsert_node(node_a)
    workspace.graph.upsert_node(node_b)
    edge = _make_edge(node_a, node_b, repo, snapshot)
    workspace.graph.upsert_edge(edge)

    gen = GraphManifestGenerator(workspace)
    manifest_id, artifacts = gen.generate(repo.repo_id, snapshot_id, run_id)

    assert manifest_id == f"graph:{repo.repo_id}:{snapshot_id}"
    assert artifacts, "Expected at least one artifact"
    for art in artifacts:
        assert Path(art.uri).exists(), f"Chunk file missing: {art.uri}"


def test_manifest_node_and_edge_count(
    workspace, repo: RepoRef, snapshot: SnapshotRef, snapshot_id: str, run_id: str
) -> None:
    node_a = _make_node(10, repo, snapshot)
    node_b = _make_node(11, repo, snapshot)
    workspace.graph.upsert_node(node_a)
    workspace.graph.upsert_node(node_b)
    edge = _make_edge(node_a, node_b, repo, snapshot)
    workspace.graph.upsert_edge(edge)

    gen = GraphManifestGenerator(workspace)
    gen.generate(repo.repo_id, snapshot_id, run_id)

    row = workspace.conn.execute(
        "SELECT node_count, edge_count FROM graph_manifests"
        " WHERE repo_id=? AND snapshot_id=?",
        (repo.repo_id, snapshot_id),
    ).fetchone()
    assert row is not None
    assert row["node_count"] == 2
    assert row["edge_count"] == 1


def test_manifest_generate_empty_graph(
    workspace, repo: RepoRef, snapshot: SnapshotRef, snapshot_id: str, run_id: str
) -> None:
    gen = GraphManifestGenerator(workspace)
    manifest_id, artifacts = gen.generate(repo.repo_id, snapshot_id, run_id)
    assert manifest_id == f"graph:{repo.repo_id}:{snapshot_id}"
    assert artifacts == []
