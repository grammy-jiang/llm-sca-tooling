"""SQLite-backed memory store."""

from __future__ import annotations

import json
from sqlite3 import Connection

from llm_sca_tooling.memory.models import (
    MemoryCompactionReport,
    MemoryOptInPolicy,
    OperationalLesson,
    ProjectMemoryRecord,
    ReviewState,
    TrajectoryRecord,
)
from llm_sca_tooling.storage.workspace import _now_ts


class MemoryStore:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def workspace_id(self) -> str:
        row = self.conn.execute(
            "SELECT value_json FROM workspace_metadata WHERE key='workspace_id'"
        ).fetchone()
        if row is None:
            return "workspace:unknown"
        value = json.loads(row["value_json"])
        return str(value)

    def get_policy(self) -> MemoryOptInPolicy:
        workspace_id = self.workspace_id()
        row = self.conn.execute(
            "SELECT payload_json FROM memory_policy WHERE workspace_id=?",
            (workspace_id,),
        ).fetchone()
        if row is None:
            return MemoryOptInPolicy(workspace_id=workspace_id)
        return MemoryOptInPolicy.model_validate_json(row["payload_json"])

    def set_policy(self, policy: MemoryOptInPolicy) -> MemoryOptInPolicy:
        policy = MemoryOptInPolicy.model_validate(policy.model_dump(mode="python"))
        self.conn.execute(
            """
            INSERT INTO memory_policy(workspace_id, payload_json, updated_ts)
            VALUES (?, ?, ?)
            ON CONFLICT(workspace_id) DO UPDATE SET
              payload_json=excluded.payload_json,
              updated_ts=excluded.updated_ts
            """,
            (policy.workspace_id, policy.model_dump_json(), _now_ts()),
        )
        self.conn.commit()
        return policy

    def put_trajectory(self, record: TrajectoryRecord) -> TrajectoryRecord:
        record = TrajectoryRecord.model_validate(record.model_dump(mode="python"))
        self.conn.execute(
            """
            INSERT INTO memory_trajectories(
              trajectory_id, repo_id, issue_class, outcome, utility, review_state,
              expiry_ts, source_run_id, payload_json, created_ts, updated_ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trajectory_id) DO UPDATE SET
              outcome=excluded.outcome,
              utility=excluded.utility,
              review_state=excluded.review_state,
              expiry_ts=excluded.expiry_ts,
              payload_json=excluded.payload_json,
              updated_ts=excluded.updated_ts
            """,
            (
                record.trajectory_id,
                record.repo_id,
                record.issue_class,
                record.outcome.value,
                record.utility.value,
                record.review_state.value,
                record.expiry_ts,
                record.source_run_id,
                record.model_dump_json(),
                record.created_ts,
                _now_ts(),
            ),
        )
        self.conn.commit()
        return record

    def get_trajectory(self, trajectory_id: str) -> TrajectoryRecord:
        row = self.conn.execute(
            "SELECT payload_json FROM memory_trajectories WHERE trajectory_id=?",
            (trajectory_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"trajectory not found: {trajectory_id}")
        return TrajectoryRecord.model_validate_json(row["payload_json"])

    def list_trajectories(
        self,
        repo_id: str | None = None,
        *,
        review_state: ReviewState | None = None,
    ) -> list[TrajectoryRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if repo_id:
            clauses.append("repo_id=?")
            params.append(repo_id)
        if review_state:
            clauses.append("review_state=?")
            params.append(review_state.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return [
            TrajectoryRecord.model_validate_json(row["payload_json"])
            for row in self.conn.execute(
                f"SELECT payload_json FROM memory_trajectories {where} ORDER BY created_ts",
                params,
            )
        ]

    def put_project_memory(self, record: ProjectMemoryRecord) -> ProjectMemoryRecord:
        record = ProjectMemoryRecord.model_validate(record.model_dump(mode="python"))
        self.conn.execute(
            """
            INSERT INTO project_memory_records(
              record_id, repo_id, record_type, review_state, expiry_ts, source_run_id,
              payload_json, created_ts, updated_ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(record_id) DO UPDATE SET
              review_state=excluded.review_state,
              expiry_ts=excluded.expiry_ts,
              payload_json=excluded.payload_json,
              updated_ts=excluded.updated_ts
            """,
            (
                record.record_id,
                record.repo_id,
                record.record_type.value,
                record.review_state.value,
                record.expiry_ts,
                record.source_run_id,
                record.model_dump_json(),
                record.created_ts,
                _now_ts(),
            ),
        )
        self.conn.commit()
        return record

    def list_project_memory(
        self,
        repo_id: str | None = None,
        *,
        review_state: ReviewState | None = None,
    ) -> list[ProjectMemoryRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if repo_id:
            clauses.append("repo_id=?")
            params.append(repo_id)
        if review_state:
            clauses.append("review_state=?")
            params.append(review_state.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return [
            ProjectMemoryRecord.model_validate_json(row["payload_json"])
            for row in self.conn.execute(
                f"SELECT payload_json FROM project_memory_records {where} ORDER BY created_ts",
                params,
            )
        ]

    def put_operational_lesson(self, lesson: OperationalLesson) -> OperationalLesson:
        lesson = OperationalLesson.model_validate(lesson.model_dump(mode="python"))
        self.conn.execute(
            """
            INSERT INTO operational_lessons(
              lesson_id, source_run_id, source_event_id, target_type, review_state,
              promoted_to_ref, payload_json, created_ts, updated_ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lesson_id) DO UPDATE SET
              review_state=excluded.review_state,
              promoted_to_ref=excluded.promoted_to_ref,
              payload_json=excluded.payload_json,
              updated_ts=excluded.updated_ts
            """,
            (
                lesson.lesson_id,
                lesson.source_run_id,
                lesson.source_event_id,
                lesson.target_type.value,
                lesson.review_state.value,
                lesson.promoted_to_ref,
                lesson.model_dump_json(),
                lesson.created_ts,
                _now_ts(),
            ),
        )
        self.conn.commit()
        return lesson

    def put_compaction_report(
        self, report: MemoryCompactionReport
    ) -> MemoryCompactionReport:
        report = MemoryCompactionReport.model_validate(report.model_dump(mode="python"))
        self.conn.execute(
            """
            INSERT INTO memory_compaction_reports(report_id, repo_id, dry_run, payload_json, created_ts)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                report.report_id,
                report.repo_id,
                int(report.dry_run),
                report.model_dump_json(),
                report.created_ts,
            ),
        )
        self.conn.commit()
        return report

    def last_compaction_ts(self, repo_id: str | None = None) -> str | None:
        if repo_id:
            row = self.conn.execute(
                "SELECT max(created_ts) AS ts FROM memory_compaction_reports WHERE repo_id=?",
                (repo_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT max(created_ts) AS ts FROM memory_compaction_reports"
            ).fetchone()
        return None if row is None else row["ts"]
