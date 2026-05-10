"""Shared fixtures for blast-radius tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    GraphEdgeType,
    GraphNodeType,
    IndexStatus,
)
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import (
    Provenance,
    RepoRef,
    SnapshotRef,
    SourceSpan,
)
from llm_sca_tooling.storage import WorkspaceStore, initialize_workspace

TS = "2026-05-09T00:00:00Z"


@pytest.fixture
def workspace(tmp_path: Path) -> WorkspaceStore:
    store = initialize_workspace(tmp_path / ".llm-sca")
    yield store
    store.close()


@pytest.fixture
def repo_ref(workspace: WorkspaceStore, tmp_path: Path) -> RepoRef:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    repo = workspace.repositories.register_repo(repo_root, name="demo")
    return RepoRef(
        repo_id=repo.repo_id,
        name=repo.name,
        default_branch=repo.default_branch,
    )


@pytest.fixture
def snapshot(repo_ref: RepoRef) -> SnapshotRef:
    return SnapshotRef(
        repo_id=repo_ref.repo_id,
        git_sha="0123456789abcdef0123456789abcdef01234567",
        branch="main",
        worktree_snapshot_id=None,
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )


@pytest.fixture
def provenance(repo_ref: RepoRef, snapshot: SnapshotRef) -> Provenance:
    return Provenance(
        source_tool="test",
        source_version="0.1",
        source_run_id="run:demo",
        source_event_id="event:run:demo:1",
        repo=repo_ref,
        snapshot=snapshot,
        derivation=DerivationType.PARSER,
        confidence=1.0,
        evidence_strength=EvidenceStrength.HARD_STATIC,
        created_ts=TS,
        attributes={},
    )


def make_node(
    node_id: str,
    node_type: GraphNodeType,
    repo_ref: RepoRef,
    snapshot: SnapshotRef,
    provenance: Provenance,
    *,
    file_path: str = "src/app.py",
) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        label=node_id,
        qualified_name=(
            node_id
            if node_type
            in {GraphNodeType.FUNCTION, GraphNodeType.METHOD, GraphNodeType.CLASS}
            else None
        ),
        repo=repo_ref,
        snapshot=snapshot,
        file_path=file_path,
        span=SourceSpan(file_path=file_path, start_line=1, end_line=10),
        provenance=provenance,
        properties={},
        created_ts=TS,
    )


def make_edge(
    edge_id: str,
    source: GraphNode,
    target: GraphNode,
    provenance: Provenance,
    edge_type: GraphEdgeType = GraphEdgeType.CALLS,
    confidence: float = 1.0,
) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id,
        edge_type=edge_type,
        source_id=source.node_id,
        target_id=target.node_id,
        repo=source.repo,
        snapshot=source.snapshot,
        provenance=provenance,
        confidence=confidence,
        properties={},
        created_ts=TS,
    )
