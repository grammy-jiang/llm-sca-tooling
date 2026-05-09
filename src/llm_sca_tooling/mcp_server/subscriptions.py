"""In-memory resource subscriptions."""

from __future__ import annotations

import secrets

from pydantic import Field

from llm_sca_tooling.mcp_server.errors import ResourceUnavailable
from llm_sca_tooling.mcp_server.notifications import Notification
from llm_sca_tooling.mcp_server.resource_registry import ResourceRegistry
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.storage.workspace import _now_ts


class Subscription(StrictBaseModel):
    subscription_id: str
    uri: str
    authorization_context_hash: str | None = None
    created_ts: str = Field(default_factory=_now_ts)


class SubscriptionManager:
    def __init__(self, registry: ResourceRegistry) -> None:
        self.registry = registry
        self._subscriptions: dict[str, Subscription] = {}

    def subscribe(self, uri: str, *, authorization_context_hash: str | None = None) -> Subscription:
        if not self.registry.is_subscribable(uri):
            raise ResourceUnavailable(f"resource is not subscribable: {uri}")
        subscription = Subscription(subscription_id=f"sub:{secrets.token_urlsafe(18)}", uri=uri, authorization_context_hash=authorization_context_hash)
        self._subscriptions[subscription.subscription_id] = subscription
        return subscription

    def unsubscribe(self, subscription_id: str) -> None:
        self._subscriptions.pop(subscription_id, None)

    def matching(self, notification: Notification, *, authorization_context_hash: str | None = None) -> list[Subscription]:
        if notification.uri is None:
            return list(self._subscriptions.values())
        return [
            subscription
            for subscription in self._subscriptions.values()
            if subscription.uri == notification.uri and subscription.authorization_context_hash == authorization_context_hash
        ]
