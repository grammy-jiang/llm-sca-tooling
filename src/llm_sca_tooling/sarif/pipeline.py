"""Orchestrate static-analysis SARIF ingestion into store and graph."""

from __future__ import annotations

import uuid
from pathlib import Path

from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.sarif.adapters import BanditAdapter, CodeQLAdapter, ExternalSarifImporter, SemgrepAdapter
from llm_sca_tooling.sarif.binding import AlertBinder
from llm_sca_tooling.sarif.delta import SarifDeltaComputer
from llm_sca_tooling.sarif.errors import AnalyserUnavailableError
from llm_sca_tooling.sarif.models import NormalizedSarifRun, NormalizedSeverity
from llm_sca_tooling.sarif.normalizer import SarifNormalizer
from llm_sca_tooling.sarif.warned_by import WarnedByEmitter
from llm_sca_tooling.storage.registry import RegisteredRepository
from llm_sca_tooling.storage.workspace import WorkspaceStore


class StaticAnalysisRunner:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def run(
        self,
        *,
        repo: RegisteredRepository,
        analyser: str,
        ruleset=None,
        files: list[str] | None = None,
        import_sarif_path: str | None = None,
        config: JsonObject | None = None,
        produced_by_run_id: str | None = None,
    ) -> dict:
        config = config or {}
        snapshot_record = self.workspace.snapshots.get_latest_snapshot(repo.repo_id)
        if snapshot_record is None:
            raise AnalyserUnavailableError(f"repository is not indexed: {repo.repo_id}")
        diagnostics: list[str] = []
        if analyser == "external" or import_sarif_path:
            run = ExternalSarifImporter(self.workspace).import_sarif_file(
                Path(str(import_sarif_path)),
                repo_id=repo.repo_id,
                snapshot_id=snapshot_record.snapshot_id,
                git_sha=snapshot_record.snapshot.git_sha,
                worktree_snapshot_id=snapshot_record.snapshot.worktree_snapshot_id,
                analyser_hint=config.get("analyser_hint") or (analyser if analyser != "external" else None),
            )
        else:
            log = self._run_adapter(analyser, Path(repo.root_path), ruleset=ruleset, files=files, config=config)
            run = SarifNormalizer().normalize(
                log,
                repo_id=repo.repo_id,
                snapshot_id=snapshot_record.snapshot_id,
                git_sha=snapshot_record.snapshot.git_sha,
                worktree_snapshot_id=snapshot_record.snapshot.worktree_snapshot_id,
                run_id=f"sarif:{uuid.uuid4().hex}",
                analyser_hint=analyser,
                produced_by_run_id=produced_by_run_id,
            )
        previous = self.workspace.sarif.get_latest_run(repo.repo_id, run.analyser_id, run.ruleset_id)
        if previous is None:
            prior_runs = self.workspace.sarif.list_runs(repo.repo_id, analyser_id=run.analyser_id)
            previous = prior_runs[0] if prior_runs else None
        bound = AlertBinder(self.workspace).bind_run(run)
        diagnostics.extend(diag.model_dump_json() for diag in bound.diagnostics)
        run = bound.run
        self.workspace.sarif.store_run(run)
        delta_id = None
        new_high = None
        if previous and previous.run_id != run.run_id:
            delta = SarifDeltaComputer().compute(previous, run)
            self.workspace.sarif.store_delta(delta)
            delta_id = delta.delta_id
            new_high = delta.summary.new_critical_or_high_count
            run = run.model_copy(update={"delta_from_run_id": previous.run_id}, deep=True)
            self.workspace.sarif.store_run(run)
        nodes, edges = WarnedByEmitter(self.workspace).emit_run(run)
        return {
            "run": run,
            "delta_id": delta_id,
            "new_critical_high_count": new_high if new_high is not None else sum(1 for alert in run.alerts if alert.normalized_severity in {NormalizedSeverity.CRITICAL, NormalizedSeverity.HIGH}),
            "diagnostics": [*run.invocation_diagnostics, *diagnostics],
            "bound_alert_count": bound.bound_alert_count,
            "symbol_bound_alert_count": bound.symbol_bound_alert_count,
            "nodes_emitted": len(nodes),
            "edges_emitted": len(edges),
        }

    def _run_adapter(self, analyser: str, repo_root: Path, *, ruleset, files: list[str] | None, config: JsonObject):
        adapter = {
            "semgrep": SemgrepAdapter(),
            "bandit": BanditAdapter(),
            "codeql": CodeQLAdapter(enabled=bool(config.get("enabled"))),
        }.get(analyser)
        if adapter is None:
            raise AnalyserUnavailableError(f"unknown analyser: {analyser}")
        return adapter.run(repo_root, files=files, config={**config, "ruleset": ruleset})
