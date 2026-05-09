from __future__ import annotations

from llm_sca_tooling.indexing.blame import BlameCollector
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.summaries import SummaryCache, SymbolSummaryRecord
from llm_sca_tooling.schemas.enums import DerivationType
from llm_sca_tooling.schemas.provenance import RepoRef
from llm_sca_tooling.storage.ids import snapshot_id_for
from llm_sca_tooling.storage.workspace import _now_ts


def test_core_resources_after_graph_build(mcp_server, mcp_repo) -> None:
    task = mcp_server.call_tool("graph_build", {"repo_path": str(mcp_repo)}).payload["task"]
    repo_id = mcp_server.task_result(task["task_id"])["repo_id"]
    repos = mcp_server.read_resource("code-intelligence://repos").payload
    assert repos["count"] == 1
    assert "root_path" not in repos["repositories"][0]
    assert mcp_server.read_resource("code-intelligence://schema/graph.schema.json").media_type == "application/schema+json"
    graph = mcp_server.read_resource(f"code-intelligence://graph/{repo_id}").payload
    assert graph["node_count"] > 0
    graph_slice = mcp_server.read_resource(f"code-intelligence://graph/slice/{repo_id}/src%2Fpkg%2Fcore.py").payload
    assert graph_slice["nodes"]
    build = mcp_server.read_resource(f"code-intelligence://build-evidence/{repo_id}").payload
    assert build["build_targets"]


def test_summary_and_blame_resources(mcp_server, mcp_repo) -> None:
    result = mcp_server.task_result(mcp_server.call_tool("graph_build", {"repo_path": str(mcp_repo)}).payload["task"]["task_id"])
    repo = mcp_server.workspace.repositories.get_repo(result["repo_id"])
    snapshot_record = mcp_server.workspace.snapshots.get_snapshot(result["snapshot_id"])
    repo_ref = RepoRef(repo_id=repo.repo_id, name=repo.name)
    provenance = make_provenance(source_tool="test", repo=repo_ref, snapshot=snapshot_record.snapshot)
    summary = SymbolSummaryRecord(
        summary_id="summary:test",
        repo_id=repo.repo_id,
        snapshot_id=result["snapshot_id"],
        symbol_node_id="node:test",
        symbol_path="pkg.core:caller",
        file_path="src/pkg/core.py",
        file_hash="hash",
        summary_text="Calls callee.",
        confidence=0.5,
        derivation=DerivationType.HEURISTIC,
        generator_id="test",
        created_ts=_now_ts(),
        provenance=provenance,
    )
    SummaryCache(mcp_server.workspace.storage_root / "summaries").put(summary)
    chain = BlameCollector().collect(mcp_repo, repo_ref, result["snapshot_id"], snapshot_record.snapshot, "src/pkg/core.py", provenance, mcp_server.workspace.artifact_root / "blame")
    mcp_server.workspace.artifacts.record_artifact(chain.artifact_ref, repo_id=repo.repo_id, payload_path=chain.artifact_ref.uri)
    assert mcp_server.read_resource(f"code-intelligence://summary/{repo.repo_id}/pkg.core:caller").payload["status"] == "current"
    assert mcp_server.read_resource(f"code-intelligence://blame/{repo.repo_id}/src%2Fpkg%2Fcore.py").payload["status"] == "found"


def test_invalid_file_resource_rejected(mcp_server, mcp_repo) -> None:
    repo = mcp_server.call_tool("register_repo", {"repo_path": str(mcp_repo)}).payload["repository"]
    try:
        mcp_server.read_resource(f"code-intelligence://graph/slice/{repo['repo_id']}/..%2Fsecret.py")
    except Exception as exc:
        assert "parent" in str(exc)
    else:
        raise AssertionError("unsafe path was accepted")
