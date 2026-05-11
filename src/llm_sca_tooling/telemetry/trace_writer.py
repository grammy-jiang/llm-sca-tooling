"""Session telemetry JSONL writer.

Emits events to ``.agent/traces/<session_id>.jsonl`` as newline-delimited
JSON while the session runs. Thread-safe via an internal lock.
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["TraceWriter"]

logger = get_logger(__name__)

_SENSITIVE_PATTERNS = frozenset(
    {"api_key", "token", "secret", "password", "credential", "auth", "key"}
)


def _redact(fields: dict[str, Any]) -> dict[str, Any]:
    """Replace values whose key contains a sensitive pattern."""
    return {
        k: "***REDACTED***" if any(p in k.lower() for p in _SENSITIVE_PATTERNS) else v
        for k, v in fields.items()
    }


class TraceWriter:
    """Append-only JSONL session trace writer.

    Args:
        session_id: Unique identifier for this session.
        trace_dir: Directory where trace files are written.
    """

    def __init__(self, session_id: str, trace_dir: Path) -> None:
        self._session_id = session_id
        self._trace_dir = trace_dir
        self._lock = threading.Lock()
        self._seq = 0
        self._path = trace_dir / f"{session_id}.jsonl"
        trace_dir.mkdir(parents=True, exist_ok=True)

    def emit(
        self,
        event_type: str,
        actor: str,
        stage: str,
        redaction_status: str = "not_required",
        **fields: Any,
    ) -> str:
        """Append a trace event and return the generated ``event_id``."""
        with self._lock:
            self._seq += 1
            event_id = f"evt:{uuid.uuid4().hex}"
            event: dict[str, Any] = {
                "event_id": event_id,
                "session_id": self._session_id,
                "seq": self._seq,
                "ts": datetime.now(UTC).isoformat(),
                "type": event_type,
                "actor": actor,
                "stage": stage,
                "redaction_status": redaction_status,
                **_redact(fields),
            }
            with self._path.open("ab") as f:
                f.write(orjson.dumps(event) + b"\n")
        return event_id

    def session_start(self) -> str:
        """Emit a ``session_start`` event."""
        return self.emit("session_start", actor="agent", stage="planning")

    def session_end(self, status: str = "complete") -> str:
        """Emit a ``session_end`` event."""
        return self.emit(
            "session_end", actor="agent", stage="verification", status=status
        )

    def tool_call(
        self,
        tool_name: str,
        category: str,
        policy_action: str,
        stage: str = "execution",
        **kwargs: Any,
    ) -> str:
        """Emit a ``tool_call`` event."""
        return self.emit(
            "tool_call",
            actor="agent",
            stage=stage,
            tool_name=tool_name,
            tool_category=category,
            policy_action=policy_action,
            **kwargs,
        )

    def verification_event(
        self,
        check_name: str,
        outcome: str,
        artefact_ids: list[str],
    ) -> str:
        """Emit a ``verification_event``."""
        return self.emit(
            "verification_event",
            actor="agent",
            stage="verification",
            check_name=check_name,
            outcome=outcome,
            artefact_ids=artefact_ids,
        )
