"""Operational run, event, incident, promotion, and readiness stores."""

from __future__ import annotations

import json
from sqlite3 import Connection, IntegrityError, Row

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, canonical_json
from llm_sca_tooling.schemas.enums import PolicyAction, Severity, Status
from llm_sca_tooling.schemas.harness import HarnessCondition
from llm_sca_tooling.schemas.incidents import (
    Incident,
    IncidentStatus,
    PromotionCandidate,
    PromotionReviewState,
    PromotionTargetType,
)
from llm_sca_tooling.schemas.readiness import AIReadinessReport
from llm_sca_tooling.schemas.run_records import (
    RunEvent,
    RunEventType,
    RunRecord,
    Workflow,
)
from llm_sca_tooling.storage.errors import RunEventSequenceError, RunNotFoundError
from llm_sca_tooling.storage.transactions import transaction
from llm_sca_tooling.storage.workspace import _now_ts


class RunRecordView(StrictBaseModel):
    run: RunRecord
    events: list[RunEvent] = Field(default_factory=list)


class OperationalRecord(StrictBaseModel):
    record_id: str
    kind: str
    payload: JsonObject
    repo_id: str | None = None
    run_id: str | None = None
    event_id: str | None = None
    status: str | None = None
    policy_action: PolicyAction | None = None
    severity: Severity | None = None
    incident_id: str | None = None
    created_ts: str = Field(default_factory=_now_ts)


class OperationalStore:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def create_run(self, run_record: RunRecord) -> RunRecord:
        run_record = RunRecord.model_validate(run_record.model_dump(mode="python"))
        with transaction(self.conn, "create run"):
            self.conn.execute(
                """
                INSERT INTO run_records(run_id, workflow, user_intent_hash, status, start_ts, end_ts, toolset_hash,
                  policy_id, permission_profile, harness_condition_id, final_verdict_id, run_event_count,
                  redaction_policy_json, payload_json, created_ts, updated_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_record.run_id,
                    run_record.workflow.value,
                    run_record.user_intent_hash,
                    run_record.status.value,
                    run_record.start_ts,
                    run_record.end_ts,
                    run_record.toolset_hash,
                    run_record.policy_id,
                    run_record.permission_profile,
                    run_record.harness_condition_id,
                    run_record.final_verdict_id,
                    run_record.run_event_count,
                    run_record.redaction_policy.model_dump_json(),
                    run_record.model_dump_json(),
                    run_record.created_ts,
                    _now_ts(),
                ),
            )
            for repo in run_record.repos:
                self.conn.execute(
                    "INSERT INTO run_repositories(run_id, repo_id) VALUES (?, ?)",
                    (run_record.run_id, repo.repo_id),
                )
        return run_record

    def append_run_event(self, run_id: str, event: RunEvent) -> RunEvent:
        if event.run_id != run_id:
            raise RunEventSequenceError("event run_id does not match append target")
        run = self.get_run(run_id).run
        expected_seq = run.run_event_count + 1
        if event.seq != expected_seq:
            raise RunEventSequenceError(
                f"expected event seq {expected_seq}, got {event.seq}"
            )
        with transaction(self.conn, "append run event"):
            try:
                self.conn.execute(
                    """
                    INSERT INTO run_events(event_id, run_id, seq, ts, type, actor, stage, policy_action,
                      redaction_status, token_count, wall_ms, payload_json, created_ts)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.run_id,
                        event.seq,
                        event.ts,
                        event.type.value,
                        event.actor.value,
                        event.stage,
                        event.policy_action.value if event.policy_action else None,
                        event.redaction_status.value,
                        event.token_count,
                        event.wall_ms,
                        event.model_dump_json(),
                        _now_ts(),
                    ),
                )
            except IntegrityError as exc:
                raise RunEventSequenceError(str(exc)) from exc
            data = run.model_dump(mode="python")
            data["run_event_count"] = expected_seq
            updated = RunRecord.model_validate(data)
            self._update_run_payload(updated)
        return event

    def get_run(self, run_id: str, *, include_events: bool = False) -> RunRecordView:
        row = self.conn.execute(
            "SELECT payload_json FROM run_records WHERE run_id=?", (run_id,)
        ).fetchone()
        if not row:
            raise RunNotFoundError(f"run not found: {run_id}")
        run = RunRecord.model_validate_json(row["payload_json"])
        events = self.list_run_events(run_id) if include_events else []
        return RunRecordView(run=run, events=events)

    def list_run_events(
        self,
        run_id: str,
        *,
        type: RunEventType | None = None,  # noqa: A002
        stage: str | None = None,
        after_seq: int | None = None,
        limit: int = 1000,
    ) -> list[RunEvent]:
        clauses = ["run_id=?"]
        params: list[object] = [run_id]
        if type:
            clauses.append("type=?")
            params.append(type.value)
        if stage:
            clauses.append("stage=?")
            params.append(stage)
        if after_seq is not None:
            clauses.append("seq>?")
            params.append(after_seq)
        params.append(limit)
        return [
            RunEvent.model_validate_json(row["payload_json"])
            for row in self.conn.execute(
                f"SELECT payload_json FROM run_events WHERE {' AND '.join(clauses)} ORDER BY seq LIMIT ?",
                params,
            )
        ]

    def close_run(
        self,
        run_id: str,
        status: Status,
        *,
        final_verdict_id: str | None = None,
        end_ts: str | None = None,
    ) -> RunRecord:
        run = self.get_run(run_id).run
        data = run.model_dump(mode="python")
        data.update(
            {
                "status": status,
                "end_ts": end_ts or _now_ts(),
                "final_verdict_id": final_verdict_id or run.final_verdict_id,
            }
        )
        updated = RunRecord.model_validate(data)
        self._update_run_payload(updated)
        self.conn.commit()
        return updated

    def record_harness_condition(self, condition: HarnessCondition) -> HarnessCondition:
        condition = HarnessCondition.model_validate(condition.model_dump(mode="python"))
        self.conn.execute(
            """
            INSERT INTO harness_conditions(harness_condition_id, run_id, toolset_hash, permission_profile, captured_ts, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(harness_condition_id) DO UPDATE SET payload_json=excluded.payload_json
            """,
            (
                condition.harness_condition_id,
                condition.run_id,
                condition.toolset_hash,
                condition.permission_profile,
                condition.captured_ts,
                condition.model_dump_json(),
            ),
        )
        self.conn.commit()
        return condition

    def get_harness_condition(self, harness_condition_id: str) -> HarnessCondition:
        row = self.conn.execute(
            "SELECT payload_json FROM harness_conditions WHERE harness_condition_id=?",
            (harness_condition_id,),
        ).fetchone()
        if not row:
            raise RunNotFoundError(
                f"harness condition not found: {harness_condition_id}"
            )
        return HarnessCondition.model_validate_json(row["payload_json"])

    def record_operational_record(self, record: OperationalRecord) -> OperationalRecord:
        record = OperationalRecord.model_validate(record.model_dump(mode="python"))
        self.conn.execute(
            """
            INSERT INTO operational_records(record_id, repo_id, run_id, event_id, kind, status, policy_action, severity, incident_id, payload_json, created_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(record_id) DO UPDATE SET payload_json=excluded.payload_json
            """,
            (
                record.record_id,
                record.repo_id,
                record.run_id,
                record.event_id,
                record.kind,
                record.status,
                record.policy_action.value if record.policy_action else None,
                record.severity.value if record.severity else None,
                record.incident_id,
                canonical_json(record.payload),
                record.created_ts,
            ),
        )
        self.conn.commit()
        return record

    def query_operational_records(
        self,
        repo_id: str | None = None,
        run_id: str | None = None,
        kind: str | None = None,
        *,
        time_range: tuple[str, str] | None = None,
    ) -> list[OperationalRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if repo_id:
            clauses.append("repo_id=?")
            params.append(repo_id)
        if run_id:
            clauses.append("run_id=?")
            params.append(run_id)
        if kind:
            clauses.append("kind=?")
            params.append(kind)
        if time_range:
            clauses.append("created_ts >= ?")
            params.append(time_range[0])
            clauses.append("created_ts <= ?")
            params.append(time_range[1])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return [
            self._operational_from_row(row)
            for row in self.conn.execute(
                f"SELECT * FROM operational_records {where} ORDER BY created_ts", params
            )
        ]

    def record_incident(
        self, incident: Incident, *, primary_repo_id: str | None = None
    ) -> Incident:
        incident = Incident.model_validate(incident.model_dump(mode="python"))
        with transaction(self.conn, "record incident"):
            self.conn.execute(
                """
                INSERT INTO incidents(incident_id, severity, status, title, primary_repo_id, opened_ts, closed_ts, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET payload_json=excluded.payload_json
                """,
                (
                    incident.incident_id,
                    incident.severity.value,
                    incident.status.value,
                    incident.title,
                    primary_repo_id,
                    incident.timeline[0].ts if incident.timeline else _now_ts(),
                    incident.closed_ts,
                    incident.model_dump_json(),
                ),
            )
            for run_id in incident.source_run_ids:
                self.conn.execute(
                    "INSERT OR IGNORE INTO incident_runs(incident_id, run_id) VALUES (?, ?)",
                    (incident.incident_id, run_id),
                )
            for event_id in incident.source_event_ids:
                self.conn.execute(
                    "INSERT OR IGNORE INTO incident_events(incident_id, event_id) VALUES (?, ?)",
                    (incident.incident_id, event_id),
                )
        return incident

    def get_incident(self, incident_id: str) -> Incident:
        row = self.conn.execute(
            "SELECT payload_json FROM incidents WHERE incident_id=?", (incident_id,)
        ).fetchone()
        if not row:
            raise RunNotFoundError(f"incident not found: {incident_id}")
        return Incident.model_validate_json(row["payload_json"])

    def query_incidents(
        self,
        repo_id: str | None = None,
        status: IncidentStatus | None = None,
        severity: Severity | None = None,
        *,
        time_range: tuple[str, str] | None = None,
    ) -> list[Incident]:
        clauses: list[str] = []
        params: list[object] = []
        if repo_id:
            clauses.append("primary_repo_id=?")
            params.append(repo_id)
        if status:
            clauses.append("status=?")
            params.append(status.value)
        if severity:
            clauses.append("severity=?")
            params.append(severity.value)
        if time_range:
            clauses.append("opened_ts >= ?")
            params.append(time_range[0])
            clauses.append("opened_ts <= ?")
            params.append(time_range[1])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return [
            Incident.model_validate_json(row["payload_json"])
            for row in self.conn.execute(
                f"SELECT payload_json FROM incidents {where} ORDER BY opened_ts", params
            )
        ]

    def record_promotion_candidate(
        self, candidate: PromotionCandidate
    ) -> PromotionCandidate:
        candidate = PromotionCandidate.model_validate(
            candidate.model_dump(mode="python")
        )
        self.conn.execute(
            """
            INSERT INTO promotion_records(promotion_id, source_run_id, target_type, review_state, owner, expires_ts, payload_json, created_ts, updated_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(promotion_id) DO UPDATE SET payload_json=excluded.payload_json, updated_ts=excluded.updated_ts
            """,
            (
                candidate.promotion_id,
                candidate.source_run_id,
                candidate.target_type.value,
                candidate.review_state.value,
                candidate.owner,
                candidate.expires_ts,
                candidate.model_dump_json(),
                _now_ts(),
                _now_ts(),
            ),
        )
        self.conn.commit()
        return candidate

    def query_promotion_candidates(
        self,
        source_run_id: str | None = None,
        target_type: PromotionTargetType | None = None,
        review_state: PromotionReviewState | None = None,
    ) -> list[PromotionCandidate]:
        clauses: list[str] = []
        params: list[object] = []
        if source_run_id:
            clauses.append("source_run_id=?")
            params.append(source_run_id)
        if target_type:
            clauses.append("target_type=?")
            params.append(target_type.value)
        if review_state:
            clauses.append("review_state=?")
            params.append(review_state.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return [
            PromotionCandidate.model_validate_json(row["payload_json"])
            for row in self.conn.execute(
                f"SELECT payload_json FROM promotion_records {where}", params
            )
        ]

    def record_readiness_report(self, report: AIReadinessReport) -> AIReadinessReport:
        report = AIReadinessReport.model_validate(report.model_dump(mode="python"))
        self.conn.execute(
            """
            INSERT INTO readiness_reports(readiness_report_id, repo_id, stage, total_score, threshold_status, no_regression_status, payload_json, created_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(readiness_report_id) DO UPDATE SET payload_json=excluded.payload_json
            """,
            (
                report.readiness_report_id,
                report.repo.repo_id,
                report.stage.value,
                report.total_score,
                "passed" if report.threshold_result.passed else "failed",
                "passed" if report.no_regression_result.passed else "failed",
                report.model_dump_json(),
                _now_ts(),
            ),
        )
        self.conn.commit()
        return report

    def query_readiness_reports(
        self, repo_id: str, *, limit: int | None = None
    ) -> list[AIReadinessReport]:
        sql = "SELECT payload_json FROM readiness_reports WHERE repo_id=? ORDER BY created_ts DESC"
        params: list[object] = [repo_id]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [
            AIReadinessReport.model_validate_json(row["payload_json"])
            for row in self.conn.execute(sql, params)
        ]

    def query_runs(
        self,
        *,
        repo_id: str | None = None,
        workflow: Workflow | None = None,
        status: Status | None = None,
        incident_id: str | None = None,
        start_ts: str | None = None,
        end_ts: str | None = None,
    ) -> list[RunRecord]:
        joins = []
        clauses: list[str] = []
        params: list[object] = []
        if repo_id:
            joins.append("JOIN run_repositories rr ON rr.run_id = r.run_id")
            clauses.append("rr.repo_id=?")
            params.append(repo_id)
        if incident_id:
            joins.append("JOIN incident_runs ir ON ir.run_id = r.run_id")
            clauses.append("ir.incident_id=?")
            params.append(incident_id)
        if workflow:
            clauses.append("r.workflow=?")
            params.append(workflow.value)
        if status:
            clauses.append("r.status=?")
            params.append(status.value)
        if start_ts:
            clauses.append("r.start_ts>=?")
            params.append(start_ts)
        if end_ts:
            clauses.append("r.start_ts<=?")
            params.append(end_ts)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT DISTINCT r.payload_json FROM run_records r {' '.join(joins)} {where} ORDER BY r.start_ts"
        return [
            RunRecord.model_validate_json(row["payload_json"])
            for row in self.conn.execute(sql, params)
        ]

    def _update_run_payload(self, run: RunRecord) -> None:
        self.conn.execute(
            """
            UPDATE run_records SET status=?, end_ts=?, final_verdict_id=?, run_event_count=?, payload_json=?, updated_ts=?
            WHERE run_id=?
            """,
            (
                run.status.value,
                run.end_ts,
                run.final_verdict_id,
                run.run_event_count,
                run.model_dump_json(),
                _now_ts(),
                run.run_id,
            ),
        )

    def _operational_from_row(self, row: Row) -> OperationalRecord:
        return OperationalRecord(
            record_id=row["record_id"],
            repo_id=row["repo_id"],
            run_id=row["run_id"],
            event_id=row["event_id"],
            kind=row["kind"],
            status=row["status"],
            policy_action=(
                PolicyAction(row["policy_action"]) if row["policy_action"] else None
            ),
            severity=Severity(row["severity"]) if row["severity"] else None,
            incident_id=row["incident_id"],
            payload=json.loads(row["payload_json"]),
            created_ts=row["created_ts"],
        )
