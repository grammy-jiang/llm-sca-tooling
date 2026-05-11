"""Resource subscription recovery after client disconnect.

``SubscriptionRecoveryManager`` persists per-client subscription state and
replays missed ``notifications/resources/updated`` events on reconnect.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["SubscriptionRecoveryManager", "SubscriptionState"]

logger = get_logger(__name__)

_RESYNC_EVENT = "notifications/resources/list_changed"
_UPDATE_EVENT = "notifications/resources/updated"


@dataclass
class NotificationRecord:
    resource_uri: str
    ts: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubscriptionState:
    client_id: str
    resource_uri: str
    last_received_ts: str | None = None


class SubscriptionRecoveryManager:
    """Track subscription state and recover missed notifications on reconnect.

    On reconnect the manager compares the client's ``last_received_ts``
    against the stored notification log.  Missed events are replayed in
    order.  If the gap is older than *retention_window_seconds* a full
    re-sync event is sent instead.

    Args:
        retention_window_seconds: How long notification history is kept.
    """

    def __init__(self, retention_window_seconds: int = 3600) -> None:
        self._retention_window = retention_window_seconds
        # client_id -> resource_uri -> SubscriptionState
        self._subscriptions: dict[str, dict[str, SubscriptionState]] = defaultdict(dict)
        # resource_uri -> list[NotificationRecord] (chronological)
        self._log: dict[str, list[NotificationRecord]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(self, client_id: str, resource_uri: str) -> None:
        """Register a subscription for *client_id* to *resource_uri*."""
        self._subscriptions[client_id][resource_uri] = SubscriptionState(
            client_id=client_id,
            resource_uri=resource_uri,
        )
        logger.debug("subscribe: client=%s uri=%s", client_id, resource_uri)

    def unsubscribe(self, client_id: str, resource_uri: str) -> None:
        """Remove the subscription."""
        self._subscriptions[client_id].pop(resource_uri, None)

    # ------------------------------------------------------------------
    # Notification recording
    # ------------------------------------------------------------------

    def record_notification(
        self,
        resource_uri: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Record that a notification was emitted for *resource_uri*."""
        record = NotificationRecord(
            resource_uri=resource_uri,
            ts=datetime.now(UTC).isoformat(),
            payload=payload or {},
        )
        self._log[resource_uri].append(record)
        logger.debug("recorded notification: uri=%s ts=%s", resource_uri, record.ts)

    def acknowledge(self, client_id: str, resource_uri: str, ts: str) -> None:
        """Update the last-received timestamp for *client_id*."""
        state = self._subscriptions[client_id].get(resource_uri)
        if state is not None:
            state.last_received_ts = ts

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    def recover(
        self,
        client_id: str,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return missed notifications for all subscribed resources.

        Returns a mapping ``{resource_uri: [events]}`` where each event is
        either an ``_UPDATE_EVENT`` record or a single ``_RESYNC_EVENT``
        when the gap is too large.
        """
        result: dict[str, list[dict[str, Any]]] = {}
        subscriptions = self._subscriptions.get(client_id, {})
        now = datetime.now(UTC)

        for resource_uri, state in subscriptions.items():
            log = self._log.get(resource_uri, [])
            if not log:
                result[resource_uri] = []
                continue

            if state.last_received_ts is None:
                result[resource_uri] = [
                    {"type": _RESYNC_EVENT, "resource_uri": resource_uri}
                ]
                continue

            cutoff_ts = state.last_received_ts
            # Find events after cutoff
            missed = [r for r in log if r.ts > cutoff_ts]

            if not missed:
                result[resource_uri] = []
                continue

            # Check if the oldest missed event is within retention window
            oldest_ts = datetime.fromisoformat(missed[0].ts)
            gap_seconds = (now - oldest_ts).total_seconds()
            if gap_seconds > self._retention_window:
                result[resource_uri] = [
                    {"type": _RESYNC_EVENT, "resource_uri": resource_uri}
                ]
            else:
                result[resource_uri] = [
                    {
                        "type": _UPDATE_EVENT,
                        "resource_uri": resource_uri,
                        "ts": r.ts,
                        "payload": r.payload,
                    }
                    for r in missed
                ]

        logger.info("recovery: client=%s resources=%d", client_id, len(result))
        return result
