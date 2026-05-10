"""SQLite eval-run store."""

from __future__ import annotations

import json
from sqlite3 import Connection

import jsonschema

from llm_sca_tooling.evaluation.models import EvalRun
from llm_sca_tooling.storage.workspace import _now_ts


class EvalRunStore:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def record_eval_run(self, run: EvalRun) -> EvalRun:
        payload = run.model_dump(mode="json")
        jsonschema.validate(payload, EvalRun.model_json_schema())
        now = _now_ts()
        self.conn.execute(
            """
            INSERT INTO eval_runs(
              eval_run_id, suite_id, status, harness_condition_id,
              started_ts, completed_ts, payload_json, created_ts, updated_ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(eval_run_id) DO UPDATE SET
              suite_id=excluded.suite_id,
              status=excluded.status,
              harness_condition_id=excluded.harness_condition_id,
              started_ts=excluded.started_ts,
              completed_ts=excluded.completed_ts,
              payload_json=excluded.payload_json,
              updated_ts=excluded.updated_ts
            """,
            (
                run.eval_run_id,
                run.suite_id,
                run.status.value,
                run.harness_condition_id,
                run.start_ts,
                run.end_ts,
                json.dumps(payload, sort_keys=True),
                now,
                now,
            ),
        )
        self.conn.commit()
        return self.get_eval_run(run.eval_run_id)

    def get_eval_run(self, eval_run_id: str) -> EvalRun:
        row = self.conn.execute(
            "SELECT payload_json FROM eval_runs WHERE eval_run_id=?",
            (eval_run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(eval_run_id)
        return EvalRun.model_validate(json.loads(row["payload_json"]))

    def list_eval_runs(self, *, limit: int = 50) -> list[EvalRun]:
        return [
            EvalRun.model_validate(json.loads(row["payload_json"]))
            for row in self.conn.execute(
                "SELECT payload_json FROM eval_runs ORDER BY created_ts DESC LIMIT ?",
                (limit,),
            )
        ]
