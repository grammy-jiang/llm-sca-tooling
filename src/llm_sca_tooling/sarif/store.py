"""SQLite-backed SARIF run and delta store."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from sqlite3 import Connection

from llm_sca_tooling.schemas.base import canonical_json
from llm_sca_tooling.sarif.models import NormalizedAlert, NormalizedSarifRun, NormalizedSeverity, SEVERITY_RANK, SarifDelta
from llm_sca_tooling.sarif.normalizer import artifact_ref_for_raw_sarif
from llm_sca_tooling.storage.workspace import _now_ts


class SarifRunStore:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def store_run(self, run: NormalizedSarifRun) -> str:
        payload = run.model_dump(mode="json")
        artifact_id = run.raw_sarif_artifact_ref.artifact_id if run.raw_sarif_artifact_ref else None
        self.conn.execute(
            """
            INSERT INTO sarif_runs(
              run_id, repo_id, snapshot_id, git_sha, worktree_snapshot_id, analyser_id,
              analyser_version, analyser_name, ruleset_id, ruleset_name,
              invocation_start_ts, invocation_end_ts, invocation_exit_code, invocation_successful,
              alert_count, rule_count, raw_sarif_artifact_id, produced_by_run_id,
              delta_from_run_id, payload_json, created_ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
              alert_count=excluded.alert_count,
              rule_count=excluded.rule_count,
              payload_json=excluded.payload_json
            """,
            (
                run.run_id,
                run.repo_id,
                run.snapshot_id,
                run.git_sha,
                run.worktree_snapshot_id,
                run.analyser_id,
                run.analyser_version,
                run.analyser_name,
                run.ruleset_id,
                run.ruleset_name,
                run.invocation_start_ts,
                run.invocation_end_ts,
                run.invocation_exit_code,
                int(run.invocation_successful),
                len(run.alerts),
                len(run.rules),
                artifact_id,
                run.produced_by_run_id,
                run.delta_from_run_id,
                canonical_json(payload),
                _now_ts(),
            ),
        )
        self.conn.execute("DELETE FROM sarif_rules WHERE run_id=?", (run.run_id,))
        self.conn.execute("DELETE FROM sarif_alerts WHERE run_id=?", (run.run_id,))
        for rule in run.rules:
            self.conn.execute(
                """
                INSERT INTO sarif_rules(rule_pk, run_id, rule_id, analyser_id, name, short_description,
                  normalized_severity, cwe_ids_json, owasp_json, rule_family, predicate_id, tags_json,
                  enabled, rule_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{run.run_id}:{rule.rule_id}",
                    run.run_id,
                    rule.rule_id,
                    rule.analyser_id,
                    rule.name,
                    rule.short_description,
                    rule.normalized_severity.value,
                    json.dumps(rule.cwe_ids, sort_keys=True),
                    json.dumps(rule.owasp_categories, sort_keys=True),
                    rule.rule_family,
                    rule.predicate_id,
                    json.dumps(rule.tags, sort_keys=True),
                    int(rule.enabled),
                    rule.model_dump_json(),
                ),
            )
        for alert in run.alerts:
            self.conn.execute(
                """
                INSERT INTO sarif_alerts(alert_pk, alert_id, run_id, rule_id, analyser_id, normalized_severity,
                  message, file_path, start_line, start_column, end_line, end_column, suppressed,
                  fingerprint, baseline_state, bound_file_node_id, bound_symbol_ids_json,
                  binding_confidence, alert_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{run.run_id}:{alert.alert_id}",
                    alert.alert_id,
                    run.run_id,
                    alert.rule_id,
                    alert.analyser_id,
                    alert.normalized_severity.value,
                    alert.message,
                    alert.file_path,
                    alert.start_line,
                    alert.start_column,
                    alert.end_line,
                    alert.end_column,
                    int(alert.suppressed),
                    alert.fingerprint,
                    alert.baseline_state,
                    alert.bound_file_node_id,
                    json.dumps(alert.bound_symbol_node_ids, sort_keys=True),
                    alert.binding_confidence,
                    alert.model_dump_json(),
                ),
            )
        self.conn.commit()
        return run.run_id

    def record_raw_sarif_artifact(self, path: str | Path):
        file_path = Path(path)
        data = file_path.read_bytes()
        return artifact_ref_for_raw_sarif(str(file_path), sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))

    def get_run(self, run_id: str) -> NormalizedSarifRun | None:
        row = self.conn.execute("SELECT payload_json FROM sarif_runs WHERE run_id=?", (run_id,)).fetchone()
        return None if row is None else NormalizedSarifRun.model_validate_json(row["payload_json"])

    def list_runs(self, repo_id: str, analyser_id: str | None = None, since_ts: str | None = None) -> list[NormalizedSarifRun]:
        clauses = ["repo_id=?"]
        params: list[object] = [repo_id]
        if analyser_id:
            clauses.append("analyser_id=?")
            params.append(analyser_id)
        if since_ts:
            clauses.append("created_ts>=?")
            params.append(since_ts)
        return [
            NormalizedSarifRun.model_validate_json(row["payload_json"])
            for row in self.conn.execute(f"SELECT payload_json FROM sarif_runs WHERE {' AND '.join(clauses)} ORDER BY created_ts DESC, run_id DESC", params)
        ]

    def get_alerts(self, run_id: str, severity_min: NormalizedSeverity | None = None) -> list[NormalizedAlert]:
        alerts = [NormalizedAlert.model_validate_json(row["alert_json"]) for row in self.conn.execute("SELECT alert_json FROM sarif_alerts WHERE run_id=? ORDER BY file_path, start_line, alert_id", (run_id,))]
        if severity_min is not None:
            alerts = [alert for alert in alerts if SEVERITY_RANK[alert.normalized_severity] >= SEVERITY_RANK[severity_min]]
        return alerts

    def get_alerts_for_file(self, repo_id: str, file_path: str, active_run_ids: list[str] | None = None) -> list[NormalizedAlert]:
        params: list[object] = [repo_id, file_path]
        run_filter = ""
        if active_run_ids:
            run_filter = f" AND a.run_id IN ({','.join('?' for _ in active_run_ids)})"
            params.extend(active_run_ids)
        rows = self.conn.execute(
            f"SELECT a.alert_json FROM sarif_alerts a JOIN sarif_runs r ON r.run_id=a.run_id WHERE r.repo_id=? AND a.file_path=?{run_filter}",
            params,
        ).fetchall()
        return [NormalizedAlert.model_validate_json(row["alert_json"]) for row in rows]

    def get_alerts_for_symbol(self, symbol_node_id: str) -> list[NormalizedAlert]:
        rows = self.conn.execute("SELECT alert_json FROM sarif_alerts WHERE bound_symbol_ids_json LIKE ?", (f"%{symbol_node_id}%",)).fetchall()
        return [alert for alert in (NormalizedAlert.model_validate_json(row["alert_json"]) for row in rows) if symbol_node_id in alert.bound_symbol_node_ids]

    def get_latest_run(self, repo_id: str, analyser_id: str, ruleset_id: str) -> NormalizedSarifRun | None:
        row = self.conn.execute(
            "SELECT payload_json FROM sarif_runs WHERE repo_id=? AND analyser_id=? AND ruleset_id=? ORDER BY created_ts DESC LIMIT 1",
            (repo_id, analyser_id, ruleset_id),
        ).fetchone()
        return None if row is None else NormalizedSarifRun.model_validate_json(row["payload_json"])

    def delete_run(self, run_id: str) -> None:
        self.conn.execute("DELETE FROM sarif_alerts WHERE run_id=?", (run_id,))
        self.conn.execute("DELETE FROM sarif_rules WHERE run_id=?", (run_id,))
        self.conn.execute("DELETE FROM sarif_runs WHERE run_id=?", (run_id,))
        self.conn.commit()

    def store_delta(self, delta: SarifDelta) -> str:
        summary = delta.summary
        self.conn.execute(
            """
            INSERT INTO sarif_deltas(delta_id, before_run_id, after_run_id, repo_id, appeared_count,
              disappeared_count, unchanged_count, changed_count, new_critical_high_count,
              fixed_critical_high_count, delta_json, computed_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(delta_id) DO UPDATE SET delta_json=excluded.delta_json
            """,
            (
                delta.delta_id,
                delta.before_run_id,
                delta.after_run_id,
                delta.repo_id,
                summary.appeared_count,
                summary.disappeared_count,
                summary.unchanged_count,
                summary.changed_count,
                summary.new_critical_or_high_count,
                summary.fixed_critical_or_high_count,
                delta.model_dump_json(),
                delta.computed_ts,
            ),
        )
        self.conn.commit()
        return delta.delta_id

    def get_delta(self, delta_id: str) -> SarifDelta | None:
        row = self.conn.execute("SELECT delta_json FROM sarif_deltas WHERE delta_id=?", (delta_id,)).fetchone()
        return None if row is None else SarifDelta.model_validate_json(row["delta_json"])
