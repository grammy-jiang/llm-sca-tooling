"""SARIF resource payload helpers."""

from __future__ import annotations

from collections import Counter, defaultdict

from llm_sca_tooling.sarif.models import NormalizedSarifRun, SarifDelta


def sarif_run_resource_payload(
    run: NormalizedSarifRun, delta: SarifDelta | None = None
) -> dict:
    severity_summary = Counter(alert.normalized_severity.value for alert in run.alerts)
    alerts_by_file: dict[str, list[dict]] = defaultdict(list)
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
        "invocation_start_ts": run.invocation_start_ts,
        "invocation_successful": run.invocation_successful,
        "alert_count": len(run.alerts),
        "rule_count": len(run.rules),
        "severity_summary": dict(severity_summary),
        "alerts_by_file": dict(alerts_by_file),
        "rules": [
            {
                "rule_id": rule.rule_id,
                "normalized_severity": rule.normalized_severity.value,
                "rule_family": rule.rule_family,
                "cwe_ids": rule.cwe_ids,
                "predicate_id": rule.predicate_id,
                "tags": rule.tags,
            }
            for rule in run.rules
        ],
        "delta_from_run_id": run.delta_from_run_id,
        "delta_summary": delta.summary.model_dump(mode="json") if delta else None,
        "sarif_artifact_ref": (
            run.raw_sarif_artifact_ref.model_dump(mode="json")
            if run.raw_sarif_artifact_ref
            else None
        ),
        "produced_by_run_id": run.produced_by_run_id,
        "schema_version": "0.1.0",
    }
