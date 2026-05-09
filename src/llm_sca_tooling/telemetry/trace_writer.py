"""File-based session telemetry writer."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

import orjson

from llm_sca_tooling.config import redact_sensitive_fields


class TraceWriter:
    """Append Phase H0-compatible session events to a JSONL trace file."""

    def __init__(self, session_id: str, trace_dir: Path) -> None:
        if not session_id.strip():
            raise ValueError("session_id must be non-empty")
        self.session_id = session_id
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.trace_dir / f"{session_id}.jsonl"
        self._seq = 0
        self._lock = threading.Lock()

    def emit(self, event_type: str, actor: str, stage: str, **fields: object) -> None:
        """Append a trace event to the session JSONL file."""

        with self._lock:
            self._seq += 1
            event = {
                "event_id": f"event:{uuid.uuid4()}",
                "session_id": self.session_id,
                "seq": self._seq,
                "ts": _utc_now(),
                "type": event_type,
                "actor": actor,
                "stage": stage,
                "redaction_status": fields.pop("redaction_status", "not_required"),
            }
            event.update(fields)
            safe_event = redact_sensitive_fields(event)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(_json_line(safe_event))

    def session_start(self) -> None:
        self.emit("session_start", "agent", "planning")

    def session_end(self, status: str) -> None:
        self.emit("session_end", "agent", "review", status=status)

    def tool_call(
        self, tool_name: str, category: str, policy_action: str, **kwargs: object
    ) -> None:
        self.emit(
            "tool_call",
            "tool",
            str(kwargs.pop("stage", "execution")),
            tool_name=tool_name,
            tool_category=category,
            policy_action=policy_action,
            **kwargs,
        )

    def verification_event(
        self, check_name: str, outcome: str, artefact_ids: list[str]
    ) -> None:
        self.emit(
            "verification_event",
            "tool",
            "verification",
            check_name=check_name,
            outcome=outcome,
            artefact_ids=artefact_ids,
        )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_line(value: object) -> str:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS).decode("utf-8") + "\n"
