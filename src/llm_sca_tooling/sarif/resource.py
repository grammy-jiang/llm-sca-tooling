"""SARIF MCP resource payload helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from llm_sca_tooling.sarif.models import NormalizedSarifRun
from llm_sca_tooling.sarif.store import SarifRunStore

__all__ = ["sarif_run_resource", "sarif_run_summaries"]


async def sarif_run_resource(
    store: SarifRunStore, repo_id: str, run_id: str
) -> dict[str, Any]:
    run = await store.get_run(run_id)
    if run is None or run.repo_id != repo_id:
        raise KeyError(run_id)
    return _payload(run)


async def sarif_run_summaries(
    store: SarifRunStore, repo_id: str
) -> list[dict[str, Any]]:
    return await store.list_runs(repo_id)


def _payload(run: NormalizedSarifRun) -> dict[str, Any]:
    severity = Counter(alert.normalized_severity.value for alert in run.alerts)
    alerts_by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for alert in run.alerts:
        alerts_by_file[alert.file_path or "<unresolved>"].append(
            {
                "alert_id": alert.alert_id,
                "rule_id": alert.rule_id,
                "normalized_severity": alert.normalized_severity.value,
                "message": alert.message,
                "start_line": alert.start_line,
                "end_line": alert.end_line,
                "suppressed": alert.suppressed,
                "bound_symbol_ids": alert.bound_symbol_node_ids,
                "binding_confidence": alert.binding_confidence,
                "baseline_state": alert.baseline_state,
            }
        )
    return {
        "run_id": run.run_id,
        "repo_id": run.repo_id,
        "snapshot_id": run.snapshot_id,
        "git_sha": run.git_sha,
        "analyser_id": run.analyser_id,
        "analyser_version": run.analyser_version,
        "analyser_name": run.analyser_name,
        "ruleset_id": run.ruleset_id,
        "ruleset_name": run.ruleset_name,
        "invocation_successful": run.invocation_successful,
        "alert_count": len(run.alerts),
        "rule_count": len(run.rules),
        "severity_summary": dict(severity),
        "alerts_by_file": dict(alerts_by_file),
        "rules": [rule.model_dump(mode="json") for rule in run.rules],
        "delta_from_run_id": run.delta_from_run_id,
        "sarif_artifact_ref": run.raw_sarif_artifact_ref,
        "produced_by_run_id": run.produced_by_run_id,
        "schema_version": "0.1.0",
    }
