"""Resource subscription recovery."""

from __future__ import annotations

from llm_sca_tooling.hardening.models import SubscriptionRecoveryState
from llm_sca_tooling.schemas.base import JsonObject


class SubscriptionRecoveryManager:
    def __init__(self) -> None:
        self.states: dict[tuple[str, str], SubscriptionRecoveryState] = {}
        self.events: list[JsonObject] = []

    def record_state(self, state: SubscriptionRecoveryState) -> None:
        self.states[(state.client_id, state.resource_uri)] = state

    def record_event(self, *, resource_uri: str, ts: str, payload: JsonObject) -> None:
        self.events.append({"resource_uri": resource_uri, "ts": ts, "payload": payload})

    def missed_events(self, *, client_id: str, resource_uri: str) -> list[JsonObject]:
        state = self.states.get((client_id, resource_uri))
        if state is None:
            return [{"type": "resources/list_changed", "resource_uri": resource_uri}]
        return [
            event
            for event in self.events
            if event["resource_uri"] == resource_uri
            and str(event["ts"]) > state.last_seen_ts
        ]
