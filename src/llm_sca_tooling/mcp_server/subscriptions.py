"""Subscription validation facade."""

from __future__ import annotations

from llm_sca_tooling.mcp_server.errors import ResourceNotFound
from llm_sca_tooling.mcp_server.notifications import NotificationManager
from llm_sca_tooling.mcp_server.resource_registry import ResourceRegistry

__all__ = ["SubscriptionManager"]


class SubscriptionManager:
    def __init__(
        self, resources: ResourceRegistry, notifications: NotificationManager
    ) -> None:
        self._resources = resources
        self._notifications = notifications

    def subscribe(self, uri: str) -> None:
        descriptors = self._resources.list_descriptors()
        if not any(
            uri.startswith(d.uri_template.split("{", 1)[0]) for d in descriptors
        ):
            raise ResourceNotFound(f"Resource {uri!r} is not subscribable")
        self._notifications.subscribe(uri)

    def unsubscribe(self, uri: str) -> None:
        self._notifications.unsubscribe(uri)

    def list_subscriptions(self) -> list[str]:
        return self._notifications.list_subscriptions()
