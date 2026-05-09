"""Task manager facade."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.task_runner import TaskRunner
from llm_sca_tooling.mcp_server.task_store import TaskRecord, TaskStore
from llm_sca_tooling.mcp_server.telemetry import TelemetryRecorder
from llm_sca_tooling.storage import WorkspaceStore


class TaskManager:
    def __init__(self, workspace: WorkspaceStore, config: McpServerConfig, telemetry: TelemetryRecorder) -> None:
        self.store = TaskStore(workspace, default_ttl_seconds=config.task_ttl_seconds_default, poll_interval_seconds=config.task_poll_interval_seconds)
        self.runner = TaskRunner(self.store, telemetry)
        self.config = config

    def recover_inflight(self) -> int:
        return self.store.recover_inflight()

    def status(self, task_id: str, *, authorization_context_hash: str | None = None) -> TaskRecord:
        return self.store.get(task_id, authorization_context_hash=authorization_context_hash)

    def result(self, task_id: str, *, authorization_context_hash: str | None = None) -> dict[str, Any]:
        record = self.status(task_id, authorization_context_hash=authorization_context_hash)
        return self.store.load_result(record)

    def cancel(self, task_id: str, *, authorization_context_hash: str | None = None) -> TaskRecord:
        return self.runner.cancel(task_id, authorization_context_hash=authorization_context_hash)

    def list(self) -> list[TaskRecord]:
        return self.store.list(allow=self.config.enable_task_list or self.config.single_user)
