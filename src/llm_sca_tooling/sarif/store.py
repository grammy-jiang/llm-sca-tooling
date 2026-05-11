"""SQLite-backed SARIF run store."""

from __future__ import annotations

from typing import Any

import orjson
from sqlalchemy import text

from llm_sca_tooling.sarif.models import (
    NormalizedAlert,
    NormalizedSarifRun,
    NormalizedSeverity,
    SarifDelta,
)
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["SarifRunStore"]

_SEVERITY_ORDER = {
    "informational": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


class SarifRunStore:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self._workspace = workspace

    async def store_run(self, run: NormalizedSarifRun) -> str:
        await self._ensure_schema()
        payload = run.model_dump(mode="json")
        async with self._workspace._session_factory() as session, session.begin():
            await session.execute(
                text("""
                    INSERT OR REPLACE INTO sarif_runs
                    (run_id, repo_id, snapshot_id, git_sha, analyser_id, analyser_name,
                     ruleset_id, alert_count, rule_count, run_json, created_ts)
                    VALUES (:run_id, :repo_id, :snapshot_id, :git_sha, :analyser_id,
                            :analyser_name, :ruleset_id, :alert_count, :rule_count,
                            :run_json, datetime('now'))
                    """),
                {
                    "run_id": run.run_id,
                    "repo_id": run.repo_id,
                    "snapshot_id": run.snapshot_id,
                    "git_sha": run.git_sha,
                    "analyser_id": run.analyser_id,
                    "analyser_name": run.analyser_name,
                    "ruleset_id": run.ruleset_id,
                    "alert_count": len(run.alerts),
                    "rule_count": len(run.rules),
                    "run_json": _dumps(payload),
                },
            )
            for rule in run.rules:
                await session.execute(
                    text("""
                        INSERT OR REPLACE INTO sarif_rules
                        (rule_pk, run_id, rule_id, analyser_id, normalized_severity,
                         rule_family, predicate_id, rule_json)
                        VALUES (:rule_pk, :run_id, :rule_id, :analyser_id,
                                :normalized_severity, :rule_family, :predicate_id,
                                :rule_json)
                        """),
                    {
                        "rule_pk": f"{run.run_id}:{rule.rule_id}",
                        "run_id": run.run_id,
                        "rule_id": rule.rule_id,
                        "analyser_id": rule.analyser_id,
                        "normalized_severity": rule.normalized_severity.value,
                        "rule_family": rule.rule_family,
                        "predicate_id": rule.predicate_id,
                        "rule_json": _dumps(rule.model_dump(mode="json")),
                    },
                )
            for alert in run.alerts:
                await session.execute(
                    text("""
                        INSERT OR REPLACE INTO sarif_alerts
                        (alert_id, run_id, rule_id, analyser_id, normalized_severity,
                         message, file_path, start_line, suppressed, fingerprint,
                         bound_file_node_id, bound_symbol_ids_json, binding_confidence,
                         alert_json)
                        VALUES (:alert_id, :run_id, :rule_id, :analyser_id,
                                :normalized_severity, :message, :file_path, :start_line,
                                :suppressed, :fingerprint,
                                :bound_file_node_id, :bound_symbol_ids_json,
                                :binding_confidence, :alert_json)
                        """),
                    {
                        "alert_id": alert.alert_id,
                        "run_id": run.run_id,
                        "rule_id": alert.rule_id,
                        "analyser_id": alert.analyser_id,
                        "normalized_severity": alert.normalized_severity.value,
                        "message": alert.message,
                        "file_path": alert.file_path,
                        "start_line": alert.start_line,
                        "suppressed": int(alert.suppressed),
                        "fingerprint": alert.fingerprint,
                        "bound_file_node_id": alert.bound_file_node_id,
                        "bound_symbol_ids_json": _dumps(alert.bound_symbol_node_ids),
                        "binding_confidence": alert.binding_confidence,
                        "alert_json": _dumps(alert.model_dump(mode="json")),
                    },
                )
        return run.run_id

    async def get_run(self, run_id: str) -> NormalizedSarifRun | None:
        await self._ensure_schema()
        async with self._workspace._session_factory() as session:
            row = (
                await session.execute(
                    text("SELECT run_json FROM sarif_runs WHERE run_id = :run_id"),
                    {"run_id": run_id},
                )
            ).first()
        return NormalizedSarifRun.model_validate(_loads(row[0])) if row else None

    async def list_runs(
        self, repo_id: str, analyser_id: str | None = None
    ) -> list[dict[str, Any]]:
        await self._ensure_schema()
        query = (
            "SELECT run_id, repo_id, analyser_id, alert_count, rule_count, created_ts "
            "FROM sarif_runs WHERE repo_id = :repo_id"
        )
        params = {"repo_id": repo_id}
        if analyser_id:
            query += " AND analyser_id = :analyser_id"
            params["analyser_id"] = analyser_id
        query += " ORDER BY created_ts DESC"
        async with self._workspace._session_factory() as session:
            rows = (await session.execute(text(query), params)).all()
        return [
            {
                "run_id": str(row[0]),
                "repo_id": str(row[1]),
                "analyser_id": str(row[2]),
                "alert_count": int(row[3]),
                "rule_count": int(row[4]),
                "created_ts": str(row[5]),
            }
            for row in rows
        ]

    async def get_alerts(
        self, run_id: str, severity_min: NormalizedSeverity | None = None
    ) -> list[NormalizedAlert]:
        await self._ensure_schema()
        async with self._workspace._session_factory() as session:
            rows = (
                await session.execute(
                    text("SELECT alert_json FROM sarif_alerts WHERE run_id = :run_id"),
                    {"run_id": run_id},
                )
            ).all()
        alerts = [NormalizedAlert.model_validate(_loads(row[0])) for row in rows]
        if severity_min:
            minimum = _SEVERITY_ORDER[severity_min.value]
            alerts = [
                alert
                for alert in alerts
                if _SEVERITY_ORDER[alert.normalized_severity.value] >= minimum
            ]
        return alerts

    async def get_alerts_for_file(
        self, repo_id: str, file_path: str, active_run_ids: list[str] | None = None
    ) -> list[NormalizedAlert]:
        runs = active_run_ids or [
            run["run_id"] for run in await self.list_runs(repo_id)
        ]
        alerts: list[NormalizedAlert] = []
        for run_id in runs:
            alerts.extend(
                alert
                for alert in await self.get_alerts(run_id)
                if alert.file_path == file_path
            )
        return alerts

    async def get_alerts_for_symbol(self, symbol_node_id: str) -> list[NormalizedAlert]:
        await self._ensure_schema()
        async with self._workspace._session_factory() as session:
            rows = (
                await session.execute(text("SELECT alert_json FROM sarif_alerts"))
            ).all()
        return [
            alert
            for row in rows
            if symbol_node_id
            in (
                alert := NormalizedAlert.model_validate(_loads(row[0]))
            ).bound_symbol_node_ids
        ]

    async def get_latest_run(
        self, repo_id: str, analyser_id: str, ruleset_id: str
    ) -> NormalizedSarifRun | None:
        await self._ensure_schema()
        async with self._workspace._session_factory() as session:
            row = (
                await session.execute(
                    text("""
                        SELECT run_json FROM sarif_runs
                        WHERE repo_id = :repo_id AND analyser_id = :analyser_id
                          AND ruleset_id = :ruleset_id
                        ORDER BY created_ts DESC LIMIT 1
                        """),
                    {
                        "repo_id": repo_id,
                        "analyser_id": analyser_id,
                        "ruleset_id": ruleset_id,
                    },
                )
            ).first()
        return NormalizedSarifRun.model_validate(_loads(row[0])) if row else None

    async def delete_run(self, run_id: str) -> None:
        await self._ensure_schema()
        async with self._workspace._session_factory() as session, session.begin():
            await session.execute(
                text("DELETE FROM sarif_alerts WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            await session.execute(
                text("DELETE FROM sarif_rules WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            await session.execute(
                text("DELETE FROM sarif_runs WHERE run_id = :run_id"),
                {"run_id": run_id},
            )

    async def store_delta(self, delta: SarifDelta) -> str:
        await self._ensure_schema()
        async with self._workspace._session_factory() as session, session.begin():
            await session.execute(
                text("""
                    INSERT OR REPLACE INTO sarif_deltas
                    (delta_id, before_run_id, after_run_id, repo_id,
                     delta_json, computed_ts)
                    VALUES (:delta_id, :before_run_id, :after_run_id, :repo_id,
                            :delta_json, :computed_ts)
                    """),
                {
                    "delta_id": delta.delta_id,
                    "before_run_id": delta.before_run_id,
                    "after_run_id": delta.after_run_id,
                    "repo_id": delta.repo_id,
                    "delta_json": _dumps(delta.model_dump(mode="json")),
                    "computed_ts": delta.computed_ts,
                },
            )
        return delta.delta_id

    async def get_delta(self, delta_id: str) -> SarifDelta | None:
        await self._ensure_schema()
        async with self._workspace._session_factory() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT delta_json FROM sarif_deltas WHERE delta_id = :delta_id"
                    ),
                    {"delta_id": delta_id},
                )
            ).first()
        return SarifDelta.model_validate(_loads(row[0])) if row else None

    async def _ensure_schema(self) -> None:
        async with self._workspace._session_factory() as session, session.begin():
            for statement in _SCHEMA:
                await session.execute(text(statement))


def _dumps(value: Any) -> str:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS).decode()


def _loads(value: object) -> Any:
    return orjson.loads(str(value).encode())


_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS sarif_runs (
      run_id TEXT PRIMARY KEY,
      repo_id TEXT NOT NULL,
      snapshot_id TEXT NOT NULL,
      git_sha TEXT NOT NULL,
      analyser_id TEXT NOT NULL,
      analyser_name TEXT NOT NULL,
      ruleset_id TEXT NOT NULL,
      alert_count INTEGER NOT NULL,
      rule_count INTEGER NOT NULL,
      run_json TEXT NOT NULL,
      created_ts TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sarif_rules (
      rule_pk TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      rule_id TEXT NOT NULL,
      analyser_id TEXT NOT NULL,
      normalized_severity TEXT NOT NULL,
      rule_family TEXT NOT NULL,
      predicate_id TEXT,
      rule_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sarif_alerts (
      alert_id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      rule_id TEXT NOT NULL,
      analyser_id TEXT NOT NULL,
      normalized_severity TEXT NOT NULL,
      message TEXT NOT NULL,
      file_path TEXT,
      start_line INTEGER,
      suppressed INTEGER NOT NULL,
      fingerprint TEXT NOT NULL,
      bound_file_node_id TEXT,
      bound_symbol_ids_json TEXT NOT NULL,
      binding_confidence TEXT NOT NULL,
      alert_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sarif_deltas (
      delta_id TEXT PRIMARY KEY,
      before_run_id TEXT NOT NULL,
      after_run_id TEXT NOT NULL,
      repo_id TEXT NOT NULL,
      delta_json TEXT NOT NULL,
      computed_ts TEXT NOT NULL
    )
    """,
]
