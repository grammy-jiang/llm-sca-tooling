"""Async file-based run-record writer.

Stores run records under ``.agent/runs/<run_id>/``. Phase 4A will replace
the storage backend while keeping this interface stable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.errors import ClosedRunError, LLMSCAError
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["RunRecord", "RunRecordWriter"]

logger = get_logger(__name__)

_BASE_DIR = Path(".agent/runs")


@dataclass
class RunRecord:
    run_id: str
    workflow: str
    status: str  # running | complete | failed | incomplete | unknown | budget-exhausted
    events: list[dict[str, Any]] = field(default_factory=list)
    _closed: bool = field(default=False, repr=False)


def _new_id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(data)


def _append_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as f:
        f.write(data)


class RunRecordWriter:
    """Async run-record writer backed by local files.

    Args:
        base_dir: Root directory for run storage (default ``.agent/runs``).
    """

    def __init__(self, base_dir: Path = _BASE_DIR) -> None:
        self._base = base_dir
        self._runs: dict[str, RunRecord] = {}

    async def create_run(
        self,
        workflow: str,
        repos: list[str],
        model_backend: str = "unknown",
        policy_id: str = "unknown",
        permission_profile: str = "read-only",
        context_budget: int | None = None,
        redaction_policy: str = "default",
    ) -> str:
        """Create a new run record and return its ``run_id``."""
        run_id = _new_id("run")
        record: dict[str, Any] = {
            "run_id": run_id,
            "workflow": workflow,
            "repos": repos,
            "start_ts": _now(),
            "end_ts": None,
            "status": "running",
            "model_backend": model_backend,
            "toolset_hash": "unknown",
            "policy_id": policy_id,
            "permission_profile": permission_profile,
            "context_budget": context_budget,
            "run_event_count": 0,
            "harness_condition_id": None,
            "final_verdict_id": None,
            "incident_ids": [],
            "redaction_policy": redaction_policy,
        }
        run_dir = self._base / run_id
        _write_bytes(run_dir / "run-record.json", orjson.dumps(record))
        self._runs[run_id] = RunRecord(
            run_id=run_id, workflow=workflow, status="running"
        )
        logger.info("Created run %s for workflow %r", run_id, workflow)
        return run_id

    async def append_event(
        self,
        run_id: str,
        event_type: str,
        actor: str,
        stage: str,
        policy_action: str = "not_applicable",
        **fields: Any,
    ) -> str:
        """Append a run event and return its ``event_id``."""
        run = self._runs.get(run_id)
        if run is None:
            raise LLMSCAError(f"Run {run_id!r} not found")
        if run._closed:
            raise ClosedRunError(f"Cannot append to closed run {run_id!r}")

        event_id = _new_id("evt")
        seq = len(run.events) + 1
        event: dict[str, Any] = {
            "event_id": event_id,
            "run_id": run_id,
            "seq": seq,
            "ts": _now(),
            "type": event_type,
            "actor": actor,
            "stage": stage,
            "policy_action": policy_action,
            "input_ref": fields.pop("input_ref", None),
            "output_ref": fields.pop("output_ref", None),
            "token_count": fields.pop("token_count", None),
            "wall_ms": fields.pop("wall_ms", None),
            "artefact_ids": fields.pop("artefact_ids", []),
            "redaction_status": fields.pop("redaction_status", "not_required"),
            **fields,
        }
        run.events.append(event)
        run_dir = self._base / run_id
        _append_bytes(run_dir / "events.jsonl", orjson.dumps(event) + b"\n")
        return event_id

    async def close_run(
        self,
        run_id: str,
        status: str,
        final_verdict_id: str | None = None,
        harness_condition_id: str | None = None,
    ) -> None:
        """Close a run with a final status."""
        run = self._runs.get(run_id)
        if run is None:
            raise LLMSCAError(f"Run {run_id!r} not found")
        run.status = status
        run._closed = True

        run_dir = self._base / run_id
        record_path = run_dir / "run-record.json"

        def _update() -> None:
            try:
                with record_path.open("rb") as f:
                    data: dict[str, Any] = orjson.loads(f.read())
            except OSError:
                data = {}
            data.update(
                {
                    "end_ts": _now(),
                    "status": status,
                    "run_event_count": len(run.events),
                    "final_verdict_id": final_verdict_id,
                    "harness_condition_id": harness_condition_id,
                }
            )
            _write_bytes(record_path, orjson.dumps(data))

        _update()
        logger.info("Closed run %s with status %r", run_id, status)

    async def get_run(self, run_id: str) -> RunRecord | None:
        """Return the in-memory RunRecord for *run_id*, or None if not found."""
        return self._runs.get(run_id)
