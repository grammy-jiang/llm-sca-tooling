"""Tool descriptors and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from pydantic import Field

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolNotFound
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.schemas.base import SCHEMA_VERSION, JsonObject, StrictBaseModel
from llm_sca_tooling.schemas.provenance import ArtifactRef


class ToolDescriptor(StrictBaseModel):
    name: str
    description: str
    input_schema: JsonObject
    output_schema: JsonObject
    read_only: bool
    long_running: bool = False
    task_support: str = "none"
    permission: ToolPermissionDescriptor
    emits_resource_notifications: bool = False
    emits_run_task_telemetry: bool = True


class ToolResult(StrictBaseModel):
    tool_name: str
    status: str
    payload: JsonObject
    schema_version: str = SCHEMA_VERSION
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    diagnostics: list[JsonObject] = Field(default_factory=list)
    run_event_ids: list[str] = Field(default_factory=list)
    notifications: list[JsonObject] = Field(default_factory=list)


class ToolHandler(ABC):
    descriptor: ToolDescriptor

    @abstractmethod
    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        raise NotImplementedError


class ToolRegistry:
    def __init__(self, handlers: Iterable[ToolHandler] = ()) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        for handler in handlers:
            self.register(handler)

    def register(self, handler: ToolHandler) -> None:
        if handler.descriptor.name in self._handlers:
            raise ValueError(f"duplicate tool: {handler.descriptor.name}")
        self._handlers[handler.descriptor.name] = handler

    def list_descriptors(self) -> list[ToolDescriptor]:
        return [self._handlers[name].descriptor for name in sorted(self._handlers)]

    def get(self, name: str) -> ToolHandler:
        try:
            return self._handlers[name]
        except KeyError as exc:
            raise ToolNotFound(f"tool not found: {name}") from exc

    def call(
        self, context: McpRequestContext, name: str, args: JsonObject
    ) -> ToolResult:
        return self.get(name).call(context, args)
