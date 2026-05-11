"""Trajectory and project-memory store backed by SQLite (with in-memory fallback)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from llm_sca_tooling.memory.models import (
    MemoryOptInPolicy,
    OperationalLesson,
    ProjectMemoryRecord,
    TrajectoryRecord,
)
from llm_sca_tooling.memory.policy import make_default_policy

_DDL = """
CREATE TABLE IF NOT EXISTS trajectories (
    trajectory_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_records (
    record_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lessons (
    lesson_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
"""


class MemoryStore:
    def __init__(
        self,
        workspace_id: str = "default",
        db_path: str | Path | None = None,
    ) -> None:
        self.policy: MemoryOptInPolicy = make_default_policy(workspace_id)
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.executescript(_DDL)
        self._conn.commit()

    # ── internal helpers ─────────────────────────────────────────────────────

    # Table names are literals derived from the calling code — no user input.
    _TABLES: dict[str, tuple[str, str, str]] = {
        "trajectories": (
            "INSERT OR REPLACE INTO trajectories (trajectory_id, data) VALUES (?, ?)",
            "SELECT data FROM trajectories WHERE trajectory_id = ?",
            "SELECT data FROM trajectories",
        ),
        "project_records": (
            "INSERT OR REPLACE INTO project_records (record_id, data) VALUES (?, ?)",
            "SELECT data FROM project_records WHERE record_id = ?",
            "SELECT data FROM project_records",
        ),
        "lessons": (
            "INSERT OR REPLACE INTO lessons (lesson_id, data) VALUES (?, ?)",
            "SELECT data FROM lessons WHERE lesson_id = ?",
            "SELECT data FROM lessons",
        ),
    }

    def _put(self, table: str, pk_col: str, pk: str, data: str) -> None:
        sql = self._TABLES[table][0]
        self._conn.execute(sql, (pk, data))
        self._conn.commit()

    def _get(self, table: str, pk_col: str, pk: str) -> str | None:
        sql = self._TABLES[table][1]
        row = self._conn.execute(sql, (pk,)).fetchone()
        return row[0] if row else None

    def _all(self, table: str) -> list[str]:
        sql = self._TABLES[table][2]
        return [row[0] for row in self._conn.execute(sql)]

    # ── Trajectories ──────────────────────────────────────────────────────────

    def put_trajectory(self, record: TrajectoryRecord) -> None:
        self._put(
            "trajectories",
            "trajectory_id",
            record.trajectory_id,
            record.model_dump_json(),
        )

    def get_trajectory(self, tid: str) -> TrajectoryRecord | None:
        raw = self._get("trajectories", "trajectory_id", tid)
        return TrajectoryRecord.model_validate(json.loads(raw)) if raw else None

    def all_trajectories(self, repo_id: str | None = None) -> list[TrajectoryRecord]:
        records = [
            TrajectoryRecord.model_validate(json.loads(d))
            for d in self._all("trajectories")
        ]
        if repo_id:
            records = [r for r in records if r.repo_id == repo_id]
        return records

    def update_trajectory(self, tid: str, **kwargs: object) -> TrajectoryRecord | None:
        record = self.get_trajectory(tid)
        if record is None:
            return None
        updated = record.model_copy(update=kwargs)
        self.put_trajectory(updated)
        return updated

    # ── Project memory ────────────────────────────────────────────────────────

    def put_project_record(self, record: ProjectMemoryRecord) -> None:
        self._put(
            "project_records",
            "record_id",
            record.record_id,
            record.model_dump_json(),
        )

    def approved_project_records(
        self, repo_id: str | None = None
    ) -> list[ProjectMemoryRecord]:
        records = [
            ProjectMemoryRecord.model_validate(json.loads(d))
            for d in self._all("project_records")
        ]
        records = [r for r in records if r.review_state == "approved"]
        if repo_id:
            records = [r for r in records if r.repo_id == repo_id]
        return records

    def all_project_records(
        self, repo_id: str | None = None
    ) -> list[ProjectMemoryRecord]:
        records = [
            ProjectMemoryRecord.model_validate(json.loads(d))
            for d in self._all("project_records")
        ]
        if repo_id:
            records = [r for r in records if r.repo_id == repo_id]
        return records

    # ── Lessons ───────────────────────────────────────────────────────────────

    def put_lesson(self, lesson: OperationalLesson) -> None:
        self._put("lessons", "lesson_id", lesson.lesson_id, lesson.model_dump_json())

    def get_lesson(self, lid: str) -> OperationalLesson | None:
        raw = self._get("lessons", "lesson_id", lid)
        return OperationalLesson.model_validate(json.loads(raw)) if raw else None

    def update_lesson(self, lid: str, **kwargs: object) -> OperationalLesson | None:
        lesson = self.get_lesson(lid)
        if lesson is None:
            return None
        updated = lesson.model_copy(update=kwargs)
        self.put_lesson(updated)
        return updated
