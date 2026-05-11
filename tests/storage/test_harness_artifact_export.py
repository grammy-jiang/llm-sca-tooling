"""Tests for harness metadata store, artifact store, and export/import."""

from __future__ import annotations

import orjson
import pytest

from llm_sca_tooling.schemas.base import SCHEMA_VERSION
from llm_sca_tooling.storage import WorkspaceStore
from llm_sca_tooling.storage.errors import ArtifactNotFoundError, ImportExportError
from llm_sca_tooling.storage.export_import import ExportBundle, ExportImportService

# ---------------------------------------------------------------------------
# Harness metadata store
# ---------------------------------------------------------------------------


async def test_put_and_get_harness_metadata(
    workspace: WorkspaceStore, tmp_path
) -> None:
    repo = await workspace.registry.register_repo(tmp_path)
    await workspace.harness.put_harness_metadata(
        repo.repo_id, "manifest_hashes", {"agents_md": "sha:abc"}
    )
    records = await workspace.harness.get_harness_metadata(
        repo.repo_id, "manifest_hashes"
    )
    assert len(records) == 1
    assert records[0]["agents_md"] == "sha:abc"


async def test_supply_chain_record_stored(workspace: WorkspaceStore) -> None:
    await workspace.harness.record_supply_chain_record(
        "analyser", "bandit", "1.7.0", {"version": "1.7.0"}
    )
    records = await workspace.harness.list_supply_chain_records(
        component_type="analyser"
    )
    assert any(r["name"] == "bandit" for r in records)


async def test_harness_metadata_workspace_level(workspace: WorkspaceStore) -> None:
    await workspace.harness.put_harness_metadata(
        None, "permission_profile", {"profile": "scoped-execute"}
    )
    records = await workspace.harness.get_harness_metadata(None, "permission_profile")
    assert records[0]["profile"] == "scoped-execute"


# ---------------------------------------------------------------------------
# Artifact store
# ---------------------------------------------------------------------------


async def test_record_and_get_artifact(workspace: WorkspaceStore) -> None:
    art_id = await workspace.artifacts.record_artifact(
        "art:001",
        "sarif",
        "file:///tmp/results.sarif",
        "not_required",
        sha256="deadbeef",
    )
    art = await workspace.artifacts.get_artifact(art_id)
    assert art["sha256"] == "deadbeef"


async def test_artifact_not_found(workspace: WorkspaceStore) -> None:
    with pytest.raises(ArtifactNotFoundError):
        await workspace.artifacts.get_artifact("art:nonexistent")


async def test_list_artifacts_by_kind(workspace: WorkspaceStore) -> None:
    await workspace.artifacts.record_artifact(
        "art:1", "sarif", "file:///a.sarif", "not_required"
    )
    await workspace.artifacts.record_artifact(
        "art:2", "trace", "file:///b.jsonl", "not_required"
    )
    sarif_arts = await workspace.artifacts.list_artifacts(kind="sarif")
    assert all(a["kind"] == "sarif" for a in sarif_arts)


async def test_list_artifacts_by_repo_and_run(
    workspace: WorkspaceStore, tmp_path
) -> None:
    repo = await workspace.registry.register_repo(tmp_path, name="repo")
    run_id = await workspace.operations.create_run(
        "artifact-test", repo_ids=[repo.repo_id]
    )
    await workspace.artifacts.record_artifact(
        "art:repo-run",
        "trace",
        "file:///tmp/trace.jsonl",
        "redacted",
        repo_id=repo.repo_id,
        run_id=run_id,
        size_bytes=10,
        media_type="application/jsonl",
        metadata={"phase": "test"},
    )
    matches = await workspace.artifacts.list_artifacts(
        repo_id=repo.repo_id, run_id=run_id
    )
    assert [artifact["artifact_id"] for artifact in matches] == ["art:repo-run"]


async def test_artifact_hash_verification_missing_file(
    workspace: WorkspaceStore,
) -> None:
    await workspace.artifacts.record_artifact(
        "art:hash1", "report", "/nonexistent/file.json", "not_required", sha256="abc123"
    )
    result = await workspace.artifacts.verify_artifact_hash("art:hash1")
    assert result.matched is False
    assert result.actual is None


async def test_artifact_hash_verification_no_hash_and_match(
    workspace: WorkspaceStore, tmp_path
) -> None:
    await workspace.artifacts.record_artifact(
        "art:nohash", "report", str(tmp_path / "missing.json"), "not_required"
    )
    no_hash = await workspace.artifacts.verify_artifact_hash("art:nohash")
    assert no_hash.matched is True
    assert no_hash.expected is None

    payload = tmp_path / "payload.txt"
    payload.write_text("content")
    expected = "ed7002b439e9ac845f22357d822bac1444730fbdb6016d3ec9432297b9ec9f73"
    await workspace.artifacts.record_artifact(
        "art:match", "report", f"file://{payload}", "not_required", sha256=expected
    )
    matched = await workspace.artifacts.verify_artifact_hash("art:match")
    assert matched.matched is True
    assert matched.actual == expected


async def test_artifact_hash_verification_missing_record(
    workspace: WorkspaceStore,
) -> None:
    with pytest.raises(ArtifactNotFoundError):
        await workspace.artifacts.verify_artifact_hash("art:missing")


# ---------------------------------------------------------------------------
# Export/import
# ---------------------------------------------------------------------------


async def test_export_import_round_trip(
    workspace: WorkspaceStore,
    storage_provenance,
    storage_repo_ref,
    storage_snapshot_ref,
    registered_repo,
    tmp_path,
) -> None:
    from llm_sca_tooling.schemas.graph import GraphNode, GraphNodeType

    n1 = GraphNode(
        node_id="node:ex1",
        node_type=GraphNodeType.module,
        label="app.py",
        repo=storage_repo_ref,
        snapshot=storage_snapshot_ref,
        provenance=storage_provenance,
        created_ts="2026-05-09T12:00:00Z",
    )
    await workspace.graph.add_node(n1)

    service = ExportImportService(workspace.graph)
    from llm_sca_tooling.storage.graph_queries import GraphSlice

    slice_ = GraphSlice(
        repo_id=storage_repo_ref.repo_id,
        requested_snapshot_id=None,
        snapshot_ids=[storage_snapshot_ref.git_sha or ""],
        snapshot_consistency="clean",
        nodes=[n1],
        edges=[],
        diagnostics=[],
        truncated=False,
        limit=None,
        provenance_summary="test",
    )
    bundle = service.export_slice(slice_)
    bundle_path = tmp_path / "export.json"
    service.save_bundle(bundle, bundle_path)

    # Import into a fresh workspace
    fresh = await WorkspaceStore.initialize(tmp_path / "fresh", in_memory=True)
    await fresh.registry.register_repo(tmp_path)
    await fresh.snapshots.record_snapshot(registered_repo.repo_id, git_sha="abc123")

    loaded = service.load_bundle(bundle_path)
    fresh_service = ExportImportService(fresh.graph)
    result = await fresh_service.import_bundle(loaded)
    assert result.imported_nodes == 1
    assert result.errors == []


def test_export_slice_marks_truncated(tmp_path) -> None:
    from llm_sca_tooling.storage.graph_queries import GraphSlice

    service = ExportImportService(graph_store=None)  # type: ignore[arg-type]
    bundle = service.export_slice(
        GraphSlice(
            repo_id="repo:1",
            requested_snapshot_id=None,
            snapshot_ids=["abc"],
            snapshot_consistency="clean",
            nodes=[],
            edges=[],
            diagnostics=[],
            truncated=True,
            limit=5,
            provenance_summary="test",
        )
    )
    path = tmp_path / "bundle.json"
    service.save_bundle(bundle, path)
    assert "Truncated at 5 nodes" in service.load_bundle(path).diagnostics


def test_load_bundle_rejects_missing_and_incompatible(tmp_path) -> None:
    service = ExportImportService(graph_store=None)  # type: ignore[arg-type]
    with pytest.raises(ImportExportError, match="not found"):
        service.load_bundle(tmp_path / "missing.json")

    bad = tmp_path / "bad.json"
    bad.write_bytes(
        orjson.dumps(
            {
                "export_id": "export:bad",
                "export_type": "graph_slice",
                "created_ts": "2026-05-09T12:00:00Z",
                "schema_version": "0.0.0",
                "payload": {},
            }
        )
    )
    with pytest.raises(ImportExportError, match="schema version"):
        service.load_bundle(bad)


async def test_import_bundle_rejects_invalid_payload(workspace: WorkspaceStore) -> None:
    service = ExportImportService(workspace.graph)
    bundle = ExportBundle(
        export_id="export:invalid",
        export_type="graph_slice",
        created_ts="2026-05-09T12:00:00Z",
        schema_version=SCHEMA_VERSION,
        repos=[],
        snapshots=[],
        payload={"nodes": [{"node_id": ""}], "edges": [{"edge_id": ""}]},
    )
    with pytest.raises(ImportExportError, match="Bundle validation failed"):
        await service.import_bundle(bundle)
