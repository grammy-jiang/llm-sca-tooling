from __future__ import annotations

from llm_sca_tooling.indexing.graph_slices import GraphSliceGenerator
from llm_sca_tooling.indexing.service import IndexingService, graph_build, graph_update
from llm_sca_tooling.schemas.enums import GraphNodeType, IndexStatus, Severity, Status


def test_graph_build_persists_nodes_edges_manifest_and_events(python_basic_repo, indexing_workspace) -> None:
    result = IndexingService(indexing_workspace).graph_build(python_basic_repo)
    assert result.status == "fresh"
    assert result.nodes_added > 0
    assert result.edges_added > 0
    assert result.graph_manifest_id is not None
    assert indexing_workspace.operations.get_run(result.run_id).run.status == Status.COMPLETED
    events = indexing_workspace.operations.list_run_events(result.run_id)
    assert [event.seq for event in events] == list(range(1, len(events) + 1))
    assert any(event.stage == "graph" and event.payload["persisted"] for event in events)
    manifest = indexing_workspace.conn.execute("SELECT graph_id FROM graph_manifests WHERE graph_id=?", (result.graph_manifest_id,)).fetchone()
    assert manifest is not None


def test_graph_update_reindexes_changed_files_and_records_summary_invalidations(python_basic_repo, indexing_workspace) -> None:
    service = IndexingService(indexing_workspace)
    service.graph_build(python_basic_repo)
    target = python_basic_repo / "src" / "pkg" / "helpers.py"
    target.write_text("def helper(x):\n    return x + 2\n", encoding="utf-8")
    result = service.graph_update(python_basic_repo)
    assert result.status in {"fresh", "partial"}
    assert result.changed_files == ["src/pkg/helpers.py"]
    assert result.stale_summary_count == 0
    assert any(event.stage == "summaries" for event in indexing_workspace.operations.list_run_events(result.run_id))


def test_graph_update_marks_superseded_snapshot_stale(python_basic_repo, indexing_workspace) -> None:
    service = IndexingService(indexing_workspace)
    first = service.graph_build(python_basic_repo)
    assert indexing_workspace.snapshots.get_snapshot(first.snapshot_id).snapshot.index_status == IndexStatus.FRESH
    (python_basic_repo / "src" / "pkg" / "helpers.py").write_text("def helper(x):\n    return x + 3\n", encoding="utf-8")
    second = service.graph_update(python_basic_repo)
    assert second.snapshot_id != first.snapshot_id
    old_snapshot = indexing_workspace.snapshots.get_snapshot(first.snapshot_id)
    assert old_snapshot.snapshot.index_status == IndexStatus.STALE
    assert old_snapshot.diagnostics[0]["code"] == "SUPERSEDED_BY_WORKTREE_CHANGE"


def test_backend_exception_becomes_partial_index_diagnostic(python_basic_repo, indexing_workspace) -> None:
    service = IndexingService(indexing_workspace)

    def failing_backend(*args, **kwargs):
        raise RuntimeError("fixture backend failure")

    service.python_backend.index_files = failing_backend
    result = service.graph_build(python_basic_repo)
    assert result.status == "partial"
    assert any(diagnostic.code == "BACKEND_FAILURE" and diagnostic.severity == Severity.ERROR for diagnostic in result.diagnostics)


def test_graph_slice_generator_returns_file_context(python_basic_repo, indexing_workspace) -> None:
    result = graph_build(python_basic_repo, workspace_path=indexing_workspace.storage_root)
    file_nodes = indexing_workspace.graph.fetch_nodes_by_type(repo_id=result.repo_id, snapshot_id=result.snapshot_id, node_type=GraphNodeType.FILE)
    core = next(node for node in file_nodes if node.file_path == "src/pkg/core.py")
    graph_slice = GraphSliceGenerator(indexing_workspace).by_file(repo_id=result.repo_id, file_path=core.file_path)
    assert any(node.file_path == "src/pkg/core.py" for node in graph_slice.nodes)
    assert graph_slice.edges


def test_top_level_wrappers_share_workspace(python_basic_repo, tmp_path) -> None:
    workspace = tmp_path / "workspace"
    first = graph_build(python_basic_repo, workspace_path=workspace)
    repeat = graph_build(python_basic_repo, workspace_path=workspace)
    (python_basic_repo / "src" / "pkg" / "core.py").write_text("def replacement():\n    return 1\n", encoding="utf-8")
    second = graph_update(python_basic_repo, workspace_path=workspace)
    assert first.repo_id == second.repo_id
    assert repeat.snapshot_id == first.snapshot_id
    assert second.changed_files == ["src/pkg/core.py"]
