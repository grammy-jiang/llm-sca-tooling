from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.sarif.binding import AlertBinder
from llm_sca_tooling.sarif.delta import SarifDeltaComputer
from llm_sca_tooling.sarif.normalizer import SarifNormalizer
from llm_sca_tooling.sarif.parser import SarifParser
from llm_sca_tooling.sarif.warned_by import WarnedByEmitter
from llm_sca_tooling.schemas.enums import GraphEdgeType
from llm_sca_tooling.storage.workspace import open_workspace


def _normalized(
    path: Path, *, repo_id: str, snapshot_id: str, git_sha: str | None, run_id: str
):
    return SarifNormalizer().normalize(
        SarifParser().parse_file(path),
        repo_id=repo_id,
        snapshot_id=snapshot_id,
        git_sha=git_sha,
        run_id=run_id,
        analyser_hint="semgrep",
    )


def test_store_retrieve_query_and_delete(indexed_repo, sarif_fixtures: Path) -> None:
    _, workspace_path, result = indexed_repo
    workspace = open_workspace(workspace_path)
    try:
        run = _normalized(
            sarif_fixtures / "external_generic.sarif.json",
            repo_id=result.repo_id,
            snapshot_id=result.snapshot_id,
            git_sha="abc",
            run_id="sarif:test",
        )
        workspace.sarif.store_run(run)
        assert (
            workspace.sarif.get_run("sarif:test").alerts[0].rule_id
            == "python.lang.security.audit.sqli"
        )
        assert workspace.sarif.list_runs(result.repo_id, analyser_id="semgrep")
        assert (
            workspace.sarif.get_alerts("sarif:test")[0].file_path == "src/pkg/core.py"
        )
        assert workspace.sarif.get_alerts_for_file(result.repo_id, "src/pkg/core.py")
        assert (
            workspace.sarif.get_latest_run(
                result.repo_id, "semgrep", run.ruleset_id
            ).run_id
            == "sarif:test"
        )
        workspace.sarif.delete_run("sarif:test")
        assert workspace.sarif.get_run("sarif:test") is None
    finally:
        workspace.close()


def test_binding_and_warned_by_edges(indexed_repo, sarif_fixtures: Path) -> None:
    _, workspace_path, result = indexed_repo
    workspace = open_workspace(workspace_path)
    try:
        run = _normalized(
            sarif_fixtures / "external_generic.sarif.json",
            repo_id=result.repo_id,
            snapshot_id=result.snapshot_id,
            git_sha=None,
            run_id="sarif:bind",
        )
        binding = AlertBinder(workspace).bind_run(run)
        assert binding.run.alerts[0].bound_file_node_id
        assert binding.run.alerts[0].bound_symbol_node_ids
        workspace.sarif.store_run(binding.run)
        nodes, edges = WarnedByEmitter(workspace).emit_run(binding.run)
        assert any(node.node_type.value == "sarif_alert" for node in nodes)
        assert any(edge.edge_type == GraphEdgeType.WARNED_BY for edge in edges)
        assert workspace.sarif.get_alerts_for_symbol(
            binding.run.alerts[0].bound_symbol_node_ids[0]
        )
    finally:
        workspace.close()


def test_unresolvable_alert_diagnostic(indexed_repo, sarif_fixtures: Path) -> None:
    _, workspace_path, result = indexed_repo
    workspace = open_workspace(workspace_path)
    try:
        run = _normalized(
            sarif_fixtures / "partial_locations.sarif.json",
            repo_id=result.repo_id,
            snapshot_id=result.snapshot_id,
            git_sha=None,
            run_id="sarif:unbound",
        )
        binding = AlertBinder(workspace).bind_run(run)
        assert binding.diagnostics[0].code == "SARIF_UNRESOLVABLE_LOCATION"
        assert binding.run.alerts[0].binding_confidence == "none"
    finally:
        workspace.close()


def test_delta_classifies_and_persists(indexed_repo, sarif_fixtures: Path) -> None:
    _, workspace_path, result = indexed_repo
    workspace = open_workspace(workspace_path)
    try:
        before = _normalized(
            sarif_fixtures / "delta_before.sarif.json",
            repo_id=result.repo_id,
            snapshot_id=result.snapshot_id,
            git_sha=None,
            run_id="sarif:before",
        )
        after = _normalized(
            sarif_fixtures / "delta_after.sarif.json",
            repo_id=result.repo_id,
            snapshot_id=result.snapshot_id,
            git_sha=None,
            run_id="sarif:after",
        )
        workspace.sarif.store_run(before)
        workspace.sarif.store_run(after)
        delta = SarifDeltaComputer().compute(before, after)
        workspace.sarif.store_delta(delta)
        loaded = workspace.sarif.get_delta(delta.delta_id)
        assert loaded.summary.appeared_count == 1
        assert loaded.summary.disappeared_count == 1
        assert loaded.summary.unchanged_count == 1
        assert loaded.summary.changed_count == 1
        assert loaded.summary.new_critical_or_high_count == 1
    finally:
        workspace.close()
