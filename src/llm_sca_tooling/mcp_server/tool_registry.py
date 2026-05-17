"""MCP tool registry and typed tool result models."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm_sca_tooling.mcp_server.errors import ToolNotFound
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor

__all__ = ["ToolDescriptor", "ToolRegistry", "ToolResult", "ToolHandler"]


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    read_only: bool
    long_running: bool = False
    task_support: str = "none"
    permissions: ToolPermissionDescriptor
    emits_resource_notifications: bool = False
    emits_run_task_telemetry: bool = True
    # Tier controls default visibility in tools/list responses.
    # 1 = primary workflow launchers (always visible by default)
    # 2 = infrastructure / async-polling helpers
    # 3 = evidence / query tools (internal plumbing called by Tier 1)
    # 4 = operational harness governance tools
    tier: int = 1


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    status: str
    payload: dict[str, Any]
    schema_version: str = "0.1.0"
    artifact_refs: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    run_event_ids: list[str] = Field(default_factory=list)
    notifications: list[dict[str, Any]] = Field(default_factory=list)


ToolHandler = Callable[[dict[str, Any]], Awaitable[ToolResult]]


class ToolRegistry:
    def __init__(self) -> None:
        self._descriptors: dict[str, ToolDescriptor] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, descriptor: ToolDescriptor, handler: ToolHandler) -> None:
        if descriptor.name in self._descriptors:
            raise ValueError(f"duplicate tool: {descriptor.name}")
        self._descriptors[descriptor.name] = descriptor
        self._handlers[descriptor.name] = handler

    def list_descriptors(self) -> list[ToolDescriptor]:
        return list(self._descriptors.values())

    def list_descriptors_for_tiers(self, tiers: frozenset[int]) -> list[ToolDescriptor]:
        """Return only tools whose tier is in *tiers*."""
        return [d for d in self._descriptors.values() if d.tier in tiers]

    def get_descriptor(self, name: str) -> ToolDescriptor:
        try:
            return self._descriptors[name]
        except KeyError as exc:
            raise ToolNotFound(f"Unknown tool {name!r}") from exc

    async def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        try:
            handler = self._handlers[name]
        except KeyError as exc:
            raise ToolNotFound(f"Unknown tool {name!r}") from exc
        return await handler(args)
