"""SQLite-backed eval-run artefact store."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.evaluation.models import EvalRun

__all__ = ["EvalStore"]


class EvalStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def record_eval_run(self, eval_run: EvalRun) -> None:
        self._ensure()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO eval_runs"
                "(eval_run_id, payload_json) VALUES (?, ?)",
                (
                    eval_run.eval_run_id,
                    orjson.dumps(eval_run.model_dump(mode="json")).decode(),
                ),
            )

    def get_eval_run(self, eval_run_id: str) -> EvalRun | None:
        self._ensure()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM eval_runs WHERE eval_run_id = ?",
                (eval_run_id,),
            ).fetchone()
        if row is None:
            return None
        return EvalRun.model_validate(orjson.loads(row[0]))

    def latest_eval_run(self) -> EvalRun | None:
        self._ensure()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM eval_runs ORDER BY created_rowid DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return EvalRun.model_validate(orjson.loads(row[0]))

    def resource_payload(self, eval_run_id: str) -> dict[str, Any]:
        run = (
            self.latest_eval_run()
            if eval_run_id == "latest"
            else self.get_eval_run(eval_run_id)
        )
        if run is None:
            return {"status": "not_found", "eval_run_id": eval_run_id}
        return run.model_dump(mode="json")

    def _ensure(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS eval_runs (
                    created_rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                    eval_run_id TEXT UNIQUE NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """)
