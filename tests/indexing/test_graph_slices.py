"""Tests for Phase 3 graph slice expansion."""

from __future__ import annotations

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.graph_slices import GraphSliceGenerator
from llm_sca_tooling.indexing.provenance import parser_provenance
from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import (
    IndexStatus,
    RepoRef,
    SnapshotRef,
    SourceSpan,
)
from llm_sca_tooling.storage import WorkspaceStore

NOW = "2026-05-09T12:00:00Z"


def _refs(repo_id: str) -> tuple[RepoRef, SnapshotRef]:
    repo = RepoRef(repo_id=repo_id, name="slice")
    snapshot = SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="abc123",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )
    return repo, snapshot


def _make_node(
    node_id: str,
    node_type: GraphNodeType,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    *,
    file_path: str | None = None,
    span: SourceSpan | None = None,
) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        label=node_id,
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=parser_provenance(
            repo_ref, snapshot_ref, "test", file=file_path, span=span
        ),
        created_ts=NOW,
        file_path=file_path,
        span=span,
    )


def _make_edge(
    edge_id: str,
    source_id: str,
    target_id: str,
    edge_type: GraphEdgeType,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id,
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=parser_provenance(repo_ref, snapshot_ref, "test"),
        created_ts=NOW,
    )


async def test_slice_by_file_expands_symbols_and_neighbours(
    workspace: WorkspaceStore,
    tmp_path,
) -> None:
    repo = await workspace.registry.register_repo(tmp_path, name="slice")
    await workspace.snapshots.record_snapshot(repo.repo_id, git_sha="abc123")
    repo_ref, snapshot_ref = _refs(repo.repo_id)
    file_node = _make_node(
        "node:slice-file",
        GraphNodeType.file,
        repo_ref,
        snapshot_ref,
        file_path="pkg/app.py",
        span=SourceSpan(file_path="pkg/app.py", start_line=1, end_line=20),
    )
    func_node = _make_node(
        "node:slice-func",
        GraphNodeType.function,
        repo_ref,
        snapshot_ref,
        file_path="pkg/app.py",
        span=SourceSpan(file_path="pkg/app.py", start_line=3, end_line=5),
    )
    test_node = _make_node(
        "node:slice-test",
        GraphNodeType.test,
        repo_ref,
        snapshot_ref,
        file_path="tests/test_app.py",
    )
    await workspace.graph.add_nodes([file_node, func_node, test_node])
    await workspace.graph.add_edges(
        [
            _make_edge(
                "edge:slice-contains",
                file_node.node_id,
                func_node.node_id,
                GraphEdgeType.contains,
                repo_ref,
                snapshot_ref,
            ),
            _make_edge(
                "edge:slice-tests",
                test_node.node_id,
                func_node.node_id,
                GraphEdgeType.tests,
                repo_ref,
                snapshot_ref,
            ),
        ]
    )

    generator = GraphSliceGenerator(workspace.queries, IndexingConfig())
    slice_ = await generator.slice_by_file(repo_ref.repo_id, "pkg/app.py")
    assert {node.node_id for node in slice_.nodes} >= {
        "node:slice-file",
        "node:slice-func",
        "node:slice-test",
    }
    assert slice_.snapshot_consistency == "clean"
    assert "expanded" in slice_.provenance_summary


async def test_slice_by_symbol_and_span(
    workspace: WorkspaceStore,
    tmp_path,
) -> None:
    repo = await workspace.registry.register_repo(tmp_path, name="slice")
    await workspace.snapshots.record_snapshot(repo.repo_id, git_sha="abc123")
    repo_ref, snapshot_ref = _refs(repo.repo_id)
    node = _make_node(
        "node:span-func",
        GraphNodeType.function,
        repo_ref,
        snapshot_ref,
        file_path="pkg/span.py",
        span=SourceSpan(file_path="pkg/span.py", start_line=10, end_line=12),
    )
    await workspace.graph.add_node(node)
    generator = GraphSliceGenerator(workspace.queries, IndexingConfig())
    by_symbol = await generator.slice_by_symbol("node:span-func")
    by_span = await generator.slice_by_span(repo_ref.repo_id, "pkg/span.py", 1, 20)
    assert by_symbol.nodes[0].node_id == "node:span-func"
    assert by_span.nodes[0].node_id == "node:span-func"


def test_graph_schema_imports_are_available() -> None:
    assert GraphNode is not None
    assert GraphEdge is not None
