"""File-backed run-record writer skeleton."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.config import redact_sensitive_fields

CLOSED_STATUSES = {"complete", "failed", "incomplete", "unknown", "budget-exhausted"}


@dataclass
class RunRecord:
    run_id: str
    workflow: str
    status: str
    events: list[dict[str, Any]] = field(default_factory=list)
    repos: list[str] = field(default_factory=list)
    model_backend: str = "unknown"
    policy_id: str = "default"
    permission_profile: str = "read-only"
    context_budget: int | None = None
    redaction_policy: str = "redacted"
    start_ts: str = ""
    end_ts: str | None = None
    final_verdict_id: str | None = None
    harness_condition_id: str | None = None


class RunRecordWriter:
    """Persist one JSONL file per run under `.agent/runs/` by default."""

    def __init__(self, run_dir: Path | str = Path(".agent/runs")) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def create_run(
        self,
        workflow: str,
        repos: list[str],
        model_backend: str,
        policy_id: str,
        permission_profile: str,
        context_budget: int | None,
        redaction_policy: str,
    ) -> str:
        run_id = f"run:{uuid.uuid4()}"
        record = RunRecord(
            run_id=run_id,
            workflow=workflow,
            status="running",
            repos=list(repos),
            model_backend=model_backend,
            policy_id=policy_id,
            permission_profile=permission_profile,
            context_budget=context_budget,
            redaction_policy=redaction_policy,
            start_ts=_utc_now(),
        )
        self._append_line(run_id, {"record_type": "run", "payload": record.__dict__})
        return run_id

    def append_event(
        self,
        run_id: str,
        event_type: str,
        actor: str,
        stage: str,
        policy_action: str,
        **fields: object,
    ) -> str:
        with self._lock:
            run = self.get_run(run_id)
            if run is None:
                raise RuntimeError(f"run not found: {run_id}")
            if run.status != "running":
                raise RuntimeError(f"cannot append event to closed run: {run_id}")
            seq = len(run.events) + 1
            event_id = f"event:{run_id}:{seq}"
            event = {
                "event_id": event_id,
                "run_id": run_id,
                "seq": seq,
                "ts": _utc_now(),
                "type": event_type,
                "actor": actor,
                "stage": stage,
                "policy_action": policy_action,
                "redaction_status": fields.pop("redaction_status", "not_required"),
                "input_ref": fields.pop("input_ref", None),
                "output_ref": fields.pop("output_ref", None),
                "token_count": fields.pop("token_count", None),
                "wall_ms": fields.pop("wall_ms", None),
                "artefact_ids": fields.pop("artefact_ids", []),
            }
            event.update(fields)
            self._append_line(
                run_id,
                {"record_type": "event", "payload": redact_sensitive_fields(event)},
            )
            return event_id

    def close_run(
        self,
        run_id: str,
        status: str,
        final_verdict_id: str | None = None,
        harness_condition_id: str | None = None,
    ) -> None:
        if status not in CLOSED_STATUSES:
            raise ValueError(f"unsupported closed status: {status}")
        run = self.get_run(run_id)
        if run is None:
            raise RuntimeError(f"run not found: {run_id}")
        if run.status != "running":
            raise RuntimeError(f"run already closed: {run_id}")
        self._append_line(
            run_id,
            {
                "record_type": "close",
                "payload": {
                    "status": status,
                    "end_ts": _utc_now(),
                    "final_verdict_id": final_verdict_id,
                    "harness_condition_id": harness_condition_id,
                },
            },
        )

    def get_run(self, run_id: str) -> RunRecord | None:
        path = self._run_path(run_id)
        if not path.exists():
            return None
        record: RunRecord | None = None
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            item = orjson.loads(line)
            payload = item["payload"]
            if item["record_type"] == "run":
                record = RunRecord(**payload)
            elif item["record_type"] == "event":
                events.append(payload)
            elif item["record_type"] == "close" and record is not None:
                record.status = payload["status"]
                record.end_ts = payload["end_ts"]
                record.final_verdict_id = payload.get("final_verdict_id")
                record.harness_condition_id = payload.get("harness_condition_id")
        if record is None:
            return None
        record.events = events
        return record

    def _append_line(self, run_id: str, payload: dict[str, Any]) -> None:
        with self._run_path(run_id).open("a", encoding="utf-8") as handle:
            handle.write(_json_line(payload))

    def _run_path(self, run_id: str) -> Path:
        safe_id = run_id.replace(":", "_")
        return self.run_dir / f"{safe_id}.jsonl"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_line(value: object) -> str:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS).decode("utf-8") + "\n"
