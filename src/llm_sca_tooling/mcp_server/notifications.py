"""Resource update notifications for MCP clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

__all__ = ["Notification", "NotificationManager"]


@dataclass
class Notification:
    method: str
    uri: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "uri": self.uri,
            "payload": self.payload,
            "ts": self.ts,
        }


class NotificationManager:
    def __init__(self) -> None:
        self._notifications: list[Notification] = []
        self._subscriptions: set[str] = set()

    def subscribe(self, uri: str) -> None:
        self._subscriptions.add(uri)

    def unsubscribe(self, uri: str) -> None:
        self._subscriptions.discard(uri)

    def list_subscriptions(self) -> list[str]:
        return sorted(self._subscriptions)

    def emit_updated(
        self, uri: str, payload: dict[str, Any] | None = None
    ) -> Notification:
        note = Notification("notifications/resources/updated", uri, payload or {})
        self._notifications.append(note)
        return note

    def emit_list_changed(self, uri: str = "code-intelligence://repos") -> Notification:
        note = Notification("notifications/resources/list_changed", uri)
        self._notifications.append(note)
        return note

    def drain(self) -> list[dict[str, Any]]:
        notes = [n.to_dict() for n in self._notifications]
        self._notifications.clear()
        return notes

    def peek(self) -> list[dict[str, Any]]:
        return [n.to_dict() for n in self._notifications]
