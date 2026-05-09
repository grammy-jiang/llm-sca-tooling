"""Synchronous task runner for task-capable tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from llm_sca_tooling.mcp_server.task_store import TaskProgress, TaskRecord, TaskStore
from llm_sca_tooling.mcp_server.telemetry import TelemetryRecorder
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.storage.workspace import _now_ts


class TaskRunner:
    def __init__(self, store: TaskStore, telemetry: TelemetryRecorder) -> None:
        self.store = store
        self.telemetry = telemetry

    def start(self, tool_name: str, args: JsonObject, executor: Callable[[TaskRecord], Any], *, authorization_context_hash: str | None = None, metadata: JsonObject | None = None) -> TaskRecord:
        record = self.store.create(tool_name, args, authorization_context_hash=authorization_context_hash, metadata=metadata)
        self.telemetry.record_task_event(record.task_id, "created", {"tool_name": tool_name}, status=record.status)
        return self.run(record, executor)

    def run(self, record: TaskRecord, executor: Callable[[TaskRecord], Any]) -> TaskRecord:
        if record.cancellation_requested:
            record.status = "cancelled"
            record.completed_ts = _now_ts()
            record.updated_ts = record.completed_ts
            self.store.save(record)
            return record
        record.status = "running"
        record.started_ts = _now_ts()
        record.updated_ts = record.started_ts
        record.progress.append(TaskProgress(stage="task", message="Task started", percent=0.1))
        self.store.save(record)
        self.telemetry.record_task_event(record.task_id, "started", status=record.status)
        try:
            result = executor(record)
            record = self.store.store_result(record, result)
            record.status = "completed"
            record.completed_ts = _now_ts()
            record.updated_ts = record.completed_ts
            record.progress.append(TaskProgress(stage="task", message="Task completed", percent=1.0, artifact_refs=[record.result_artifact_ref] if record.result_artifact_ref else []))
            if isinstance(result, dict):
                run_id = result.get("run_id")
                if isinstance(run_id, str):
                    record.run_id = run_id
        except Exception as exc:
            record.status = "failed"
            record.error = {"code": exc.__class__.__name__, "message": str(exc)}
            record.completed_ts = _now_ts()
            record.updated_ts = record.completed_ts
            record.progress.append(TaskProgress(stage="task", message="Task failed", percent=1.0))
        self.store.save(record)
        self.telemetry.record_task_event(record.task_id, record.status, {"run_id": record.run_id}, status=record.status)
        return record

    def cancel(self, task_id: str, *, authorization_context_hash: str | None = None) -> TaskRecord:
        record = self.store.get(task_id, authorization_context_hash=authorization_context_hash)
        record.cancellation_requested = True
        if record.status in {"queued", "running", "cancelling"}:
            record.status = "cancelled"
            record.completed_ts = _now_ts()
            record.progress.append(TaskProgress(stage="task", message="Task cancellation requested"))
        record.updated_ts = _now_ts()
        self.store.save(record)
        self.telemetry.record_task_event(record.task_id, "cancelled", status=record.status)
        return record
