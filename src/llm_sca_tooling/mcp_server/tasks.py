"""Persistent task model for long-running MCP operations."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import orjson
from pydantic import BaseModel, ConfigDict, Field

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.errors import TaskNotFound, ToolPermissionDenied
from llm_sca_tooling.mcp_server.serialization import canonical_bytes
from llm_sca_tooling.mcp_server.telemetry import McpTelemetry

__all__ = ["TaskManager", "TaskRecord", "new_task_id", "to_protocol_task"]

# Maps internal task statuses to the MCP 2025-11-25 TaskStatus enum values.
# "working" covers all in-progress states; "expired" maps to "failed".
_STATUS_MAP: dict[str, str] = {
    "created": "working",
    "queued": "working",
    "running": "working",
    "cancelling": "working",
    "cancelled": "cancelled",
    "failed": "failed",
    "completed": "completed",
    "expired": "failed",
}

TaskStatus = Literal[
    "created",
    "queued",
    "running",
    "cancelling",
    "cancelled",
    "failed",
    "completed",
    "expired",
]
TaskRunner = Callable[["TaskRecord"], Awaitable[dict[str, Any]]]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def new_task_id() -> str:
    return f"task:{secrets.token_urlsafe(32)}"


def to_protocol_task(task: TaskRecord) -> dict[str, Any]:
    """Serialise a TaskRecord to the MCP 2025-11-25 ``Task`` wire format.

    The spec defines ``Task`` as:
    ``{ taskId, status, createdAt, lastUpdatedAt, ttl, pollInterval?,
        statusMessage? }``

    Internal status values are mapped to the spec's closed enum
    (``working | completed | failed | cancelled | input_required``).
    """
    status = _STATUS_MAP.get(task.status, "working")
    result: dict[str, Any] = {
        "taskId": task.task_id,
        "status": status,
        "createdAt": task.created_ts,
        "lastUpdatedAt": task.updated_ts,
        "ttl": task.ttl_seconds * 1000,
        "pollInterval": task.poll_interval_seconds * 1000,
    }
    # Populate statusMessage for terminal states.
    if task.status == "completed":
        result["statusMessage"] = "completed"
    elif task.error:
        result["statusMessage"] = task.error.get("message", task.status)
    return result


class TaskRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    tool_name: str
    status: TaskStatus
    created_ts: str
    started_ts: str | None = None
    updated_ts: str
    completed_ts: str | None = None
    expires_ts: str
    ttl_seconds: int
    poll_interval_seconds: int
    progress: dict[str, Any] = Field(default_factory=dict)
    authorization_context_hash: str | None = None
    input_hash: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    run_id: str | None = None
    event_ids: list[str] = Field(default_factory=list)
    cancellation_requested: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskManager:
    """File-backed task manager with restart recovery."""

    def __init__(
        self,
        workspace_path: Path,
        config: McpServerConfig,
        telemetry: McpTelemetry,
    ) -> None:
        self._config = config
        self._telemetry = telemetry
        self._tasks: dict[str, TaskRecord] = {}
        self._running: dict[str, asyncio.Task[None]] = {}
        self._path = workspace_path / ".llm-sca" / "mcp_tasks.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        self.recover_inflight()

    def _load(self) -> None:
        if not self._path.exists():
            return
        data = orjson.loads(self._path.read_bytes())
        self._tasks = {
            row["task_id"]: TaskRecord.model_validate(row)
            for row in data.get("tasks", [])
        }

    def _save(self) -> None:
        payload = {"tasks": [t.model_dump(mode="json") for t in self._tasks.values()]}
        self._path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))

    def recover_inflight(self) -> None:
        changed = False
        for task in self._tasks.values():
            if task.status in {"created", "queued", "running", "cancelling"}:
                task.status = "failed"
                task.error = {
                    "code": "TaskRestartRecovery",
                    "message": "task was in-flight during server restart",
                }
                task.updated_ts = _now()
                task.completed_ts = task.updated_ts
                changed = True
        if changed:
            self._save()

    def create_task(
        self,
        tool_name: str,
        args: dict[str, Any],
        *,
        ttl_seconds: int | None = None,
        authorization_context_hash: str | None = None,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskRecord:
        ttl = min(
            ttl_seconds or self._config.task_ttl_seconds_default,
            self._config.task_ttl_seconds_max,
        )
        created = datetime.now(UTC)
        task = TaskRecord(
            task_id=new_task_id(),
            tool_name=tool_name,
            status="queued",
            created_ts=created.isoformat(),
            updated_ts=created.isoformat(),
            expires_ts=(created + timedelta(seconds=ttl)).isoformat(),
            ttl_seconds=ttl,
            poll_interval_seconds=self._config.task_poll_interval_seconds,
            progress={"stage": "queued", "percent": 0},
            authorization_context_hash=authorization_context_hash,
            input_hash=hashlib.sha256(canonical_bytes(args)).hexdigest(),
            run_id=run_id,
            metadata=metadata or {},
        )
        self._tasks[task.task_id] = task
        self._save()
        self._telemetry.record_task_event(task.task_id, "task_created", "queued")
        return task

    def submit(
        self,
        tool_name: str,
        args: dict[str, Any],
        runner: TaskRunner,
        *,
        authorization_context_hash: str | None = None,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskRecord:
        task = self.create_task(
            tool_name,
            args,
            authorization_context_hash=authorization_context_hash,
            run_id=run_id,
            metadata={"args": args, **(metadata or {})},
        )
        self._running[task.task_id] = asyncio.create_task(self._execute(task, runner))
        return task

    async def _execute(self, task: TaskRecord, runner: TaskRunner) -> None:
        try:
            self.update_progress(task.task_id, "running", percent=10)
            task.status = "running"
            task.started_ts = _now()
            task.updated_ts = task.started_ts
            self._save()
            result = await runner(task)
            if task.cancellation_requested:
                task.status = "cancelled"
                task.error = {"code": "TaskCancelled", "message": "task cancelled"}
            else:
                task.status = "completed"
                task.result = result
                task.progress = {"stage": "completed", "percent": 100}
            task.completed_ts = _now()
            task.updated_ts = task.completed_ts
            self._telemetry.record_task_event(
                task.task_id, "task_completed", task.status
            )
        except Exception as exc:  # noqa: BLE001
            task.status = "failed"
            task.error = {"code": type(exc).__name__, "message": str(exc)}
            task.completed_ts = _now()
            task.updated_ts = task.completed_ts
            self._telemetry.record_task_event(task.task_id, "task_failed", "failed")
        finally:
            self._running.pop(task.task_id, None)
            self._save()

    def update_progress(
        self,
        task_id: str,
        stage: str,
        *,
        message: str | None = None,
        percent: int | None = None,
        counts: dict[str, int] | None = None,
    ) -> TaskRecord:
        task = self.get(task_id, include_expired=True)
        task.progress = {
            "stage": stage,
            "message": message,
            "percent": percent,
            "counts": counts or {},
            "ts": _now(),
        }
        task.updated_ts = _now()
        self._save()
        self._telemetry.record_task_event(
            task_id, "task_progress", task.status, task.progress
        )
        return task

    def get(
        self,
        task_id: str,
        *,
        authorization_context_hash: str | None = None,
        include_expired: bool = False,
    ) -> TaskRecord:
        try:
            task = self._tasks[task_id]
        except KeyError as exc:
            raise TaskNotFound(f"Task {task_id!r} not found") from exc
        if (
            task.authorization_context_hash is not None
            and authorization_context_hash != task.authorization_context_hash
        ):
            raise ToolPermissionDenied("task authorization context does not match")
        if not include_expired and datetime.fromisoformat(
            task.expires_ts
        ) < datetime.now(UTC):
            task.status = "expired"
            self._save()
        return task

    def result(self, task_id: str) -> dict[str, Any]:
        task = self.get(task_id)
        if task.status != "completed":
            return {"task": task.model_dump(mode="json"), "result_available": False}
        return {
            "task": task.model_dump(mode="json", exclude={"result"}),
            "result_available": True,
            "result": task.result,
        }

    def cancel(self, task_id: str) -> TaskRecord:
        task = self.get(task_id, include_expired=True)
        task.cancellation_requested = True
        if task.status in {"created", "queued"}:
            task.status = "cancelled"
            task.completed_ts = _now()
        elif task.status == "running":
            task.status = "cancelling"
        task.updated_ts = _now()
        self._save()
        self._telemetry.record_task_event(task_id, "task_cancel_requested", task.status)
        return task

    def list_tasks(self) -> list[TaskRecord]:
        if not self._config.task_listing_allowed:
            raise ToolPermissionDenied("task listing is disabled by server policy")
        return list(self._tasks.values())
