"""Resource update notifications."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel
from llm_sca_tooling.storage.workspace import _now_ts


class Notification(StrictBaseModel):
    method: str
    uri: str | None = None
    payload: JsonObject = Field(default_factory=dict)
    ts: str = Field(default_factory=_now_ts)


class NotificationManager:
    def __init__(self) -> None:
        self._notifications: list[Notification] = []

    def resources_updated(self, *uris: str, payload: JsonObject | None = None) -> list[Notification]:
        emitted = [Notification(method="notifications/resources/updated", uri=uri, payload=payload or {}) for uri in uris]
        self._notifications.extend(emitted)
        return emitted

    def resources_list_changed(self, payload: JsonObject | None = None) -> Notification:
        notification = Notification(method="notifications/resources/list_changed", payload=payload or {})
        self._notifications.append(notification)
        return notification

    def all(self) -> list[Notification]:
        return list(self._notifications)

    def drain(self) -> list[Notification]:
        notifications = self.all()
        self._notifications.clear()
        return notifications
