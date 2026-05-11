"""Resource descriptor registry and routing primitives."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm_sca_tooling.mcp_server.errors import ResourceNotFound

__all__ = [
    "ResourceDescriptor",
    "ResourceRegistry",
    "ResourceResult",
    "ResourceHandler",
]


class ResourceDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uri_template: str
    name: str
    description: str
    media_type: str = "application/json"
    schema_family: str = "mcp"
    schema_version: str = "0.1.0"
    subscribable: bool = True
    listable: bool = True
    size_class: str = "small"
    freshness: str = "snapshot-aware"


class ResourceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uri: str
    media_type: str
    schema_version: str = "0.1.0"
    payload: dict[str, Any]
    artifact_refs: list[dict[str, Any]] = Field(default_factory=list)
    snapshot_refs: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    redaction_status: str = "not_required"
    etag: str | None = None
    updated_ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


ResourceHandler = Callable[[str], Awaitable[ResourceResult]]


class ResourceRegistry:
    """Registry of resource descriptors and read handlers."""

    def __init__(self) -> None:
        self._descriptors: dict[str, ResourceDescriptor] = {}
        self._handlers: dict[str, ResourceHandler] = {}

    def register(
        self, descriptor: ResourceDescriptor, handler: ResourceHandler
    ) -> None:
        if descriptor.uri_template in self._descriptors:
            raise ValueError(f"duplicate resource: {descriptor.uri_template}")
        self._descriptors[descriptor.uri_template] = descriptor
        self._handlers[descriptor.uri_template] = handler

    def list_descriptors(self) -> list[ResourceDescriptor]:
        return list(self._descriptors.values())

    async def read(self, uri: str) -> ResourceResult:
        templates = sorted(
            self._handlers,
            key=lambda item: len(item.split("{", 1)[0]),
            reverse=True,
        )
        for template in templates:
            handler = self._handlers[template]
            if _matches(template, uri):
                return await handler(uri)
        raise ResourceNotFound(f"No resource handler for {uri!r}")


def _matches(template: str, uri: str) -> bool:
    if "{" not in template:
        return template == uri
    template_prefix = template.split("{", 1)[0]
    return uri.startswith(template_prefix)
