from __future__ import annotations

import subprocess
from pathlib import Path

from llm_sca_tooling.indexing.service import IndexingService
from llm_sca_tooling.plugins.http_rest.openapi_parser import parse_openapi_file
from llm_sca_tooling.plugins.http_rest.url_normalizer import match_patterns, normalize_url_pattern
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType, IndexStatus
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage import initialize_workspace
from llm_sca_tooling.storage.workspace import _now_ts


def test_url_normalizer_matches_framework_styles() -> None:
    assert normalize_url_pattern("users/<int:id>/") == "/users/{id}"
    assert normalize_url_pattern("/users/:user_id") == "/users/{user_id}"
    assert match_patterns("/users/{id}", "/users/{user_id}") == "analyser"


def test_openapi_parser_extracts_routes(tmp_path: Path) -> None:
    spec = tmp_path / "openapi.yaml"
    spec.write_text("openapi: 3.0.0\npaths:\n  /users/{id}:\n    get:\n      operationId: getUser\n", encoding="utf-8")
    repo = RepoRef(repo_id="repo:test")
    snapshot = SnapshotRef(repo_id=repo.repo_id, worktree_snapshot_id="snapshot:test", dirty=True, index_status=IndexStatus.FRESH, captured_ts=_now_ts())
    records = parse_openapi_file(spec, repo_id=repo.repo_id, plugin_id="http-rest", plugin_version="0.1.0", provenance=__import__("llm_sca_tooling.indexing.provenance", fromlist=["make_provenance"]).make_provenance(source_tool="http-rest", repo=repo, snapshot=snapshot), snapshot_id="snapshot:test")
    assert records[0].interface_name == "GET /users/{id}"


def test_http_rest_graph_build_and_trace(tmp_path: Path) -> None:
    repo = _http_repo(tmp_path)
    workspace = initialize_workspace(tmp_path / "workspace")
    try:
        result = IndexingService(workspace).graph_build(repo)
        route_nodes = workspace.graph.fetch_nodes_by_type(result.repo_id, GraphNodeType.HTTP_ROUTE)
        assert route_nodes
        exposes = workspace.graph.fetch_edges_by_type(result.repo_id, GraphEdgeType.EXPOSES)
        consumes = workspace.graph.fetch_edges_by_type(result.repo_id, GraphEdgeType.CONSUMES)
        assert exposes and consumes
    finally:
        workspace.close()


def _http_repo(tmp_path: Path) -> Path:
    root = tmp_path / "http_repo"
    (root / "src").mkdir(parents=True)
    (root / "web").mkdir()
    (root / "src" / "api.py").write_text("app = object()\n\n@app.get('/users/{id}')\ndef get_user(id: str):\n    return {'id': id}\n", encoding="utf-8")
    (root / "web" / "client.ts").write_text("export function loadUser() { return fetch('/users/123'); }\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    return root
