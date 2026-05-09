from __future__ import annotations

import json

import pytest
from jsonschema import validate

from llm_sca_tooling.schemas.enums import GraphNodeType
from llm_sca_tooling.storage import initialize_workspace
from llm_sca_tooling.storage.errors import ImportExportError
from tests.storage.conftest import graph_edge, graph_node, run_event, run_record


def test_graph_export_validates_and_imports(
    workspace, tmp_path, repo_ref, snapshot, provenance
) -> None:
    one = graph_node("node:one", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance)
    two = graph_node("node:two", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance)
    workspace.graph.add_nodes([one, two])
    workspace.graph.add_edge(graph_edge("edge:one-two", one, two, provenance))
    snapshot_id = workspace.snapshots.record_snapshot(snapshot).snapshot_id
    destination = tmp_path / "export"
    bundle = workspace.exports.export_graph(repo_ref.repo_id, snapshot_id, destination)
    with open("schemas/graph.schema.json", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    validate(instance=bundle.payload["graph_document"], schema=schema)
    target = initialize_workspace(tmp_path / "imported")
    result = target.exports.import_bundle(destination)
    assert result.inserted_nodes == 2
    assert target.graph.fetch_node("node:one") is not None
    target.close()


def test_run_export_includes_events(workspace, tmp_path, repo_ref) -> None:
    workspace.operations.create_run(run_record(repo_ref))
    workspace.operations.append_run_event("run:demo", run_event(1))
    bundle = workspace.exports.export_run("run:demo", tmp_path / "run-export")
    assert bundle.payload["run"]["run_id"] == "run:demo"
    assert bundle.payload["events"][0]["seq"] == 1


def test_import_rejects_hash_mismatch(
    workspace, tmp_path, repo_ref, snapshot, provenance
) -> None:
    one = graph_node("node:one", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance)
    workspace.graph.add_node(one)
    snapshot_id = workspace.snapshots.record_snapshot(snapshot).snapshot_id
    destination = tmp_path / "export"
    workspace.exports.export_graph(repo_ref.repo_id, snapshot_id, destination)
    path = destination / "export.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["payload"]["graph_document"]["graph_id"] = "tampered"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ImportExportError):
        workspace.exports.import_bundle(destination)
