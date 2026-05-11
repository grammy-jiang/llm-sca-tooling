"""Orchestration for static-analysis SARIF ingestion and graph binding."""

from __future__ import annotations

import hashlib
from pathlib import Path

import orjson

from llm_sca_tooling.sarif.adapters.bandit import BanditAdapter
from llm_sca_tooling.sarif.adapters.external_import import ExternalSarifImporter
from llm_sca_tooling.sarif.adapters.semgrep import SemgrepAdapter
from llm_sca_tooling.sarif.binding import bind_sarif_run
from llm_sca_tooling.sarif.delta import compute_sarif_delta
from llm_sca_tooling.sarif.models import NormalizedSarifRun
from llm_sca_tooling.sarif.normalizer import normalize_sarif_log
from llm_sca_tooling.sarif.store import SarifRunStore
from llm_sca_tooling.sarif.warned_by import build_sarif_graph_facts
from llm_sca_tooling.schemas.provenance import IndexStatus, RepoRef, SnapshotRef
from llm_sca_tooling.storage.registry import RepositoryRecord
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["StaticAnalysisResult", "run_static_analysis"]


class StaticAnalysisResult(dict[str, object]):
    """Dictionary result for MCP and tests."""


async def run_static_analysis(
    workspace: WorkspaceStore,
    *,
    repo: str,
    analyser: str,
    import_sarif_path: str | None = None,
    ruleset: str | list[str] | None = None,
) -> StaticAnalysisResult:
    repo_record = await _resolve_repo(workspace, repo)
    latest = await workspace.snapshots.get_latest_snapshot(repo_record.repo_id)
    if latest is None:
        raise ValueError("repository must be indexed before static analysis")
    op_run_id = await workspace.operations.create_run(
        "run-static-analysis", repo_ids=[repo_record.repo_id]
    )
    sarif_run_id = f"sarif-run:{hashlib.sha256(op_run_id.encode()).hexdigest()[:16]}"
    artifact_ref: str | None = None
    diagnostics: list[str] = []
    if import_sarif_path:
        path = Path(import_sarif_path)
        artifact_ref = await _record_raw_artifact(
            workspace, path, repo_record.repo_id, op_run_id
        )
        normalized = ExternalSarifImporter().import_sarif_file(
            path,
            repo_root=repo_record.root_path,
            repo_id=repo_record.repo_id,
            snapshot_id=latest.snapshot_id,
            git_sha=latest.git_sha or "unknown",
            run_id=sarif_run_id,
            analyser_hint=None if analyser == "external" else analyser,
            artifact_ref=artifact_ref,
        )
    else:
        normalized, diagnostics = await _run_adapter(
            analyser,
            repo_record.root_path,
            repo_record.repo_id,
            latest.snapshot_id,
            latest.git_sha or "unknown",
            sarif_run_id,
            ruleset,
        )
    bound = await bind_sarif_run(workspace, normalized)
    normalized = bound.run.model_copy(
        update={
            "invocation_diagnostics": [
                *diagnostics,
                *[d.message for d in bound.diagnostics],
            ],
            "produced_by_run_id": op_run_id,
        }
    )
    store = SarifRunStore(workspace)
    previous = await store.get_latest_run(
        normalized.repo_id, normalized.analyser_id, normalized.ruleset_id
    )
    await store.store_run(normalized)
    delta_id = None
    new_critical_or_high_count = sum(
        1
        for alert in normalized.alerts
        if alert.normalized_severity.value in {"critical", "high"}
    )
    if previous is not None:
        delta = compute_sarif_delta(previous, normalized)
        delta_id = await store.store_delta(delta)
        new_critical_or_high_count = delta.summary.new_critical_or_high_count
        normalized = normalized.model_copy(
            update={"delta_from_run_id": previous.run_id}
        )
        await store.store_run(normalized)
    repo_ref = RepoRef(repo_id=repo_record.repo_id, name=repo_record.name)
    snapshot_ref = SnapshotRef(
        repo_id=repo_record.repo_id,
        git_sha=latest.git_sha,
        branch=latest.branch,
        dirty=latest.dirty,
        worktree_snapshot_id=latest.worktree_snapshot_id,
        index_status=IndexStatus(latest.index_status),
        captured_ts=latest.captured_ts,
    )
    nodes, edges = build_sarif_graph_facts(normalized, repo_ref, snapshot_ref)
    await workspace.graph.add_nodes(nodes)
    await workspace.graph.add_edges(edges)
    await workspace.operations.close_run(op_run_id, "completed")
    return StaticAnalysisResult(
        run_id=normalized.run_id,
        status="completed",
        alert_count=len(normalized.alerts),
        rule_count=len(normalized.rules),
        new_critical_high_count=new_critical_or_high_count,
        delta_from_run_id=normalized.delta_from_run_id,
        delta_id=delta_id,
        sarif_resource_uri=f"code-intelligence://sarif/{normalized.repo_id}/{normalized.run_id}",
        run_event_ids=[op_run_id],
        diagnostics=[
            *[{"message": d} for d in diagnostics],
            *[d.to_dict() for d in bound.diagnostics],
        ],
        artifact_ref=artifact_ref,
    )


async def _resolve_repo(workspace: WorkspaceStore, repo: str) -> RepositoryRecord:
    if Path(repo).exists():
        return await workspace.registry.register_repo(Path(repo))
    return await workspace.registry.get_repo(repo)


async def _run_adapter(
    analyser: str,
    repo_root: Path,
    repo_id: str,
    snapshot_id: str,
    git_sha: str,
    run_id: str,
    ruleset: str | list[str] | None,
) -> tuple[NormalizedSarifRun, list[str]]:
    adapter = SemgrepAdapter() if analyser == "semgrep" else BanditAdapter()
    result = await adapter.run(repo_root)
    if result.sarif_log is None:
        from llm_sca_tooling.sarif.models import (
            SarifLog,
            SarifRun,
            SarifTool,
            SarifToolComponent,
        )

        result = result.__class__(
            SarifLog(
                version="2.1.0",
                runs=[
                    SarifRun(
                        tool=SarifTool(driver=SarifToolComponent(name=analyser)),
                        results=[],
                    )
                ],
            ),
            result.diagnostics,
            result.exit_code,
            result.raw_output_path,
        )
    ruleset_id = hashlib.sha256(orjson.dumps(ruleset or "default")).hexdigest()[:16]
    assert result.sarif_log is not None
    return (
        normalize_sarif_log(
            result.sarif_log,
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            git_sha=git_sha,
            run_id=run_id,
            analyser_id=analyser,
            ruleset_id=f"ruleset:{ruleset_id}",
        ),
        result.diagnostics,
    )


async def _record_raw_artifact(
    workspace: WorkspaceStore, path: Path, repo_id: str, op_run_id: str
) -> str:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    artifact_id = f"art:sarif:{digest[:16]}"
    await workspace.artifacts.record_artifact(
        artifact_id,
        "sarif",
        path.resolve().as_uri(),
        "not_required",
        repo_id=repo_id,
        run_id=op_run_id,
        sha256=digest,
        size_bytes=len(data),
        media_type="application/sarif+json",
    )
    return artifact_id
