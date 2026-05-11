"""Integration tests for graph_build and graph_update."""

from __future__ import annotations

import shutil
from pathlib import Path

from llm_sca_tooling.indexing.git_metadata import GitMetadata
from llm_sca_tooling.indexing.service import IndexingService
from llm_sca_tooling.storage import WorkspaceStore


async def test_graph_build_indexes_python_basic(
    workspace: WorkspaceStore, python_basic_repo: Path
) -> None:
    indexer = IndexingService(workspace)
    result = await indexer.graph_build(python_basic_repo)
    assert result.status in ("fresh", "partial")
    assert result.nodes_added > 0
    assert result.files_scanned > 0
    assert result.run_id.startswith("run:")
    assert result.snapshot_id != "unknown"


async def test_graph_build_creates_run_record(
    workspace: WorkspaceStore, python_basic_repo: Path
) -> None:
    indexer = IndexingService(workspace)
    result = await indexer.graph_build(python_basic_repo)
    run = await workspace.operations.get_run(result.run_id, include_events=True)
    assert run.status == "completed"
    assert len(run.events) > 0


async def test_graph_build_registers_repo(
    workspace: WorkspaceStore, python_basic_repo: Path
) -> None:
    indexer = IndexingService(workspace)
    result = await indexer.graph_build(python_basic_repo)
    repos = await workspace.registry.list_repos()
    assert any(r.repo_id == result.repo_id for r in repos)


async def test_graph_build_records_snapshot(
    workspace: WorkspaceStore, python_basic_repo: Path
) -> None:
    indexer = IndexingService(workspace)
    result = await indexer.graph_build(python_basic_repo)
    snap = await workspace.snapshots.get_snapshot(result.snapshot_id)
    assert snap.index_status in ("fresh", "partial")


async def test_graph_build_nodes_queryable(
    workspace: WorkspaceStore, python_basic_repo: Path
) -> None:
    indexer = IndexingService(workspace)
    result = await indexer.graph_build(python_basic_repo)
    count = await workspace.queries.count_nodes(result.repo_id)
    assert count > 0


async def test_graph_build_backend_versions_recorded(
    workspace: WorkspaceStore, python_basic_repo: Path
) -> None:
    indexer = IndexingService(workspace)
    result = await indexer.graph_build(python_basic_repo)
    assert "python_ast" in result.backend_versions


async def test_graph_build_records_blame_artifacts(
    workspace: WorkspaceStore, python_basic_repo: Path, tmp_path: Path
) -> None:
    repo_copy = tmp_path / "repo"
    shutil.copytree(python_basic_repo, repo_copy)
    indexer = IndexingService(workspace)
    result = await indexer.graph_build(repo_copy)
    assert result.artifact_refs
    artifacts = await workspace.artifacts.list_artifacts(kind="blame")
    assert artifacts


async def test_graph_update_runs(
    workspace: WorkspaceStore, python_basic_repo: Path
) -> None:
    indexer = IndexingService(workspace)
    # First build
    build_result = await indexer.graph_build(python_basic_repo)
    assert build_result.status in ("fresh", "partial")
    # Update (currently falls back to full rebuild)
    update_result = await indexer.graph_update(python_basic_repo)
    assert update_result.status in ("fresh", "partial")


async def test_graph_update_indexes_only_changed_files(
    monkeypatch, workspace: WorkspaceStore, python_basic_repo: Path, tmp_path: Path
) -> None:
    repo_copy = tmp_path / "repo"
    shutil.copytree(python_basic_repo, repo_copy)

    async def clean_collect(self, repo_path: Path) -> GitMetadata:
        return GitMetadata(
            is_git_repo=True,
            git_sha="base",
            branch="main",
            dirty=False,
            changed_files=[],
            untracked_files=[],
        )

    from llm_sca_tooling.indexing.git_metadata import GitMetadataCollector

    monkeypatch.setattr(GitMetadataCollector, "collect", clean_collect)
    indexer = IndexingService(workspace)
    await indexer.graph_build(repo_copy)

    async def dirty_collect(self, repo_path: Path) -> GitMetadata:
        return GitMetadata(
            is_git_repo=True,
            git_sha="base",
            branch="main",
            dirty=True,
            changed_files=["src/pkg/core.py"],
            untracked_files=[],
        )

    monkeypatch.setattr(GitMetadataCollector, "collect", dirty_collect)
    (repo_copy / "src/pkg/core.py").write_text("def changed():\n    return 42\n")
    update_result = await indexer.graph_update(repo_copy)
    assert update_result.status in ("fresh", "partial")
    assert update_result.files_scanned == 1
    assert not any(d.code == "UPDATE_FULL_REBUILD" for d in update_result.diagnostics)
