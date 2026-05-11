"""Telemetry hooks for MCP tool calls and tasks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from llm_sca_tooling.mcp_server.serialization import canonical_bytes

__all__ = ["McpTelemetry", "TelemetryEvent"]


@dataclass
class TelemetryEvent:
    type: str
    status: str
    payload: dict[str, Any]
    redaction_status: str = "not_required"
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "status": self.status,
            "payload": self.payload,
            "redaction_status": self.redaction_status,
            "ts": self.ts,
        }


class McpTelemetry:
    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self._events: list[TelemetryEvent] = []

    def hash_args(self, args: dict[str, Any]) -> str:
        return hashlib.sha256(canonical_bytes(args)).hexdigest()

    def record_tool_call(
        self, tool_name: str, args: dict[str, Any], status: str
    ) -> TelemetryEvent | None:
        if not self.enabled:
            return None
        event = TelemetryEvent(
            type="mcp_tool_call",
            status=status,
            payload={"tool_name": tool_name, "argument_hash": self.hash_args(args)},
        )
        self._events.append(event)
        return event

    def record_task_event(
        self,
        task_id: str,
        event_type: str,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> TelemetryEvent | None:
        if not self.enabled:
            return None
        event = TelemetryEvent(
            type=event_type,
            status=status,
            payload={"task_id": task_id, **(payload or {})},
        )
        self._events.append(event)
        return event

    def list_events(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._events]
