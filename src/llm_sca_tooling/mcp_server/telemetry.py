"""MCP tool and task telemetry hooks."""

from __future__ import annotations

from llm_sca_tooling.indexing.hashing import hash_text
from llm_sca_tooling.mcp_server.serialization import to_jsonable
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import RedactionStatus
from llm_sca_tooling.storage.operations import OperationalRecord
from llm_sca_tooling.storage.workspace import WorkspaceStore, _now_ts


class TelemetryRecorder:
    def __init__(self, workspace: WorkspaceStore, *, enabled: bool = True) -> None:
        self.workspace = workspace
        self.enabled = enabled

    def record_tool_call(
        self,
        tool_name: str,
        args: JsonObject,
        status: str,
        *,
        repo_id: str | None = None,
        error_category: str | None = None,
    ) -> str | None:
        if not self.enabled:
            return None
        record_id = f"mcp-tool:{hash_text(tool_name + _now_ts(), length=24)}"
        payload = {
            "tool_name": tool_name,
            "argument_hash": hash_text(str(to_jsonable(args)), length=32),
            "status": status,
            "error_category": error_category,
            "redaction_status": RedactionStatus.REDACTED.value,
            "ts": _now_ts(),
        }
        self.workspace.operations.record_operational_record(
            OperationalRecord(
                record_id=record_id,
                kind="mcp_tool_call",
                payload=payload,
                repo_id=repo_id,
                status=status,
            )
        )
        return record_id

    def record_task_event(
        self,
        task_id: str,
        event: str,
        payload: JsonObject | None = None,
        *,
        repo_id: str | None = None,
        status: str | None = None,
    ) -> str | None:
        if not self.enabled:
            return None
        record_id = (
            f"mcp-task-event:{hash_text(task_id + event + _now_ts(), length=24)}"
        )
        event_payload = {
            "task_id": task_id,
            "event": event,
            "payload": payload or {},
            "redaction_status": RedactionStatus.REDACTED.value,
            "ts": _now_ts(),
        }
        self.workspace.operations.record_operational_record(
            OperationalRecord(
                record_id=record_id,
                kind="mcp_task_event",
                payload=event_payload,
                repo_id=repo_id,
                status=status,
            )
        )
        return record_id
