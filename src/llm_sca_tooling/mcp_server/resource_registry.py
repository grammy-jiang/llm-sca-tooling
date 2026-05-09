"""Resource descriptors and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from pydantic import Field

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ResourceInvalidUri, ResourceNotFound
from llm_sca_tooling.mcp_server.resource_uris import (
    ParsedResourceUri,
    parse_resource_uri,
)
from llm_sca_tooling.schemas.base import SCHEMA_VERSION, JsonObject, StrictBaseModel
from llm_sca_tooling.schemas.enums import RedactionStatus
from llm_sca_tooling.schemas.provenance import ArtifactRef, SnapshotRef


class ResourceDescriptor(StrictBaseModel):
    uri_template: str
    name: str
    description: str
    media_type: str = "application/json"
    schema_family: str | None = None
    schema_version: str = SCHEMA_VERSION
    subscribable: bool = True
    listable: bool = True
    size_class: str = "small"
    freshness: str = "snapshot-aware"


class ResourceResult(StrictBaseModel):
    uri: str
    media_type: str
    schema_version: str = SCHEMA_VERSION
    payload: JsonObject
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    snapshot_refs: list[SnapshotRef] = Field(default_factory=list)
    diagnostics: list[JsonObject] = Field(default_factory=list)
    redaction_status: RedactionStatus = RedactionStatus.REDACTED
    etag: str | None = None
    updated_ts: str | None = None


class ResourceHandler(ABC):
    descriptor: ResourceDescriptor

    @abstractmethod
    def matches(self, parsed: ParsedResourceUri) -> bool:
        raise NotImplementedError

    @abstractmethod
    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        raise NotImplementedError


class ResourceRegistry:
    def __init__(self, handlers: Iterable[ResourceHandler] = ()) -> None:
        self._handlers: list[ResourceHandler] = []
        for handler in handlers:
            self.register(handler)

    def register(self, handler: ResourceHandler) -> None:
        if any(
            existing.descriptor.uri_template == handler.descriptor.uri_template
            for existing in self._handlers
        ):
            raise ResourceInvalidUri(
                f"duplicate resource template: {handler.descriptor.uri_template}"
            )
        self._handlers.append(handler)

    def list_descriptors(self) -> list[ResourceDescriptor]:
        return [
            handler.descriptor
            for handler in self._handlers
            if handler.descriptor.listable
        ]

    def is_subscribable(self, uri: str) -> bool:
        handler = self._resolve(uri)
        return handler.descriptor.subscribable

    def read(self, context: McpRequestContext, uri: str) -> ResourceResult:
        parsed = parse_resource_uri(uri)
        return self._resolve_parsed(parsed).read(context, uri, parsed)

    def _resolve(self, uri: str) -> ResourceHandler:
        return self._resolve_parsed(parse_resource_uri(uri))

    def _resolve_parsed(self, parsed: ParsedResourceUri) -> ResourceHandler:
        matches = [handler for handler in self._handlers if handler.matches(parsed)]
        if not matches:
            raise ResourceNotFound(f"no resource handler for {parsed.uri}")
        if len(matches) > 1:
            raise ResourceInvalidUri(f"ambiguous resource handler for {parsed.uri}")
        return matches[0]
