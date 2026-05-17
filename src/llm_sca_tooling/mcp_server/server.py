"""MCP server runtime for the code-intelligence surface."""

from __future__ import annotations

import asyncio
from typing import Any

import fastmcp

from llm_sca_tooling.config import MCPConfig
from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.context import McpServerContext
from llm_sca_tooling.mcp_server.prompts import PromptRegistry, register_default_prompts
from llm_sca_tooling.mcp_server.resource_registry import (
    ResourceDescriptor,
    ResourceRegistry,
    ResourceResult,
)
from llm_sca_tooling.mcp_server.resources import register_core_resources
from llm_sca_tooling.mcp_server.subscriptions import SubscriptionManager
from llm_sca_tooling.mcp_server.tasks import TaskManager, to_protocol_task
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolRegistry,
    ToolResult,
)
from llm_sca_tooling.mcp_server.tools import register_core_tools
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["MCPServer"]

logger = get_logger(__name__)


def _build_mcp(name: str) -> fastmcp.FastMCP:
    mcp: fastmcp.FastMCP = fastmcp.FastMCP(name)

    @mcp.tool()
    async def health_check() -> str:
        """Health check — returns 'ok'."""
        return "ok"

    return mcp


class MCPServer:
    """Local-first MCP server with testable in-process client methods."""

    def __init__(self, config: MCPConfig | McpServerConfig | None = None) -> None:
        if isinstance(config, McpServerConfig):
            self._server_config = config
            self._config = MCPConfig()
        else:
            self._config = config or MCPConfig()
            self._server_config = McpServerConfig()
        self._mcp = _build_mcp(self._server_config.server_name)
        self._running = False
        self._context: McpServerContext | None = None
        self._resources: ResourceRegistry | None = None
        self._tools: ToolRegistry | None = None
        self._tasks: TaskManager | None = None
        self._prompts: PromptRegistry | None = None
        self._subscriptions: SubscriptionManager | None = None
        # Tiers exposed via tools/list. Default: Tier 1 (primary) + Tier 2 (infra).
        # Clients may request additional tiers via initialize
        # capabilities["tool_tiers"].
        self._tool_tiers: frozenset[int] = frozenset({1, 2})

    async def initialize(
        self, *, client_capabilities: dict[str, object] | None = None
    ) -> None:
        if self._context is not None:
            return
        # Negotiate tool tiers from client capabilities before constructing context
        if client_capabilities:
            raw = client_capabilities.get("tool_tiers")
            if isinstance(raw, list) and all(isinstance(t, int) for t in raw):
                self._tool_tiers = frozenset(raw)
        context = await McpServerContext.create(
            self._server_config, client_capabilities=client_capabilities
        )
        resources = ResourceRegistry()
        tools = ToolRegistry()
        tasks = TaskManager(
            self._server_config.workspace_path, self._server_config, context.telemetry
        )
        prompts = PromptRegistry(context.sampling)
        register_core_resources(resources, context)
        register_core_tools(tools, context, tasks)
        register_default_prompts(prompts)
        self._context = context
        self._resources = resources
        self._tools = tools
        self._tasks = tasks
        self._prompts = prompts
        self._subscriptions = SubscriptionManager(resources, context.notifications)

    def start(self, config: MCPConfig | None = None) -> None:
        """Start the MCP server synchronously via FastMCP (HTTP/dev mode)."""
        cfg = config or self._config
        logger.info(
            "MCP server started in dev mode on %s:%d",
            cfg.host,
            cfg.port,
        )
        self._running = True
        try:
            self._mcp.run()
        finally:
            self._running = False

    def start_stdio(self) -> None:
        """Start the MCP server using the stdio JSON-RPC 2.0 transport.

        All custom tools, resources, and prompts from the registered
        ToolRegistry/ResourceRegistry/PromptRegistry are exposed over
        stdin/stdout.  All log and diagnostic output goes to stderr so
        that stdout carries only JSON-RPC frames.

        This is the recommended transport for AI agent usage (Claude Code,
        Copilot CLI, Codex CLI).
        """
        from llm_sca_tooling.mcp_server.stdio_transport import (  # noqa: PLC0415
            run_stdio,
        )

        self._running = True
        try:
            asyncio.run(run_stdio(self))
        finally:
            self._running = False

    async def start_async(self, config: MCPConfig | None = None) -> None:
        """Start the MCP server asynchronously."""
        cfg = config or self._config
        logger.info(
            "MCP server (async) started in dev mode on %s:%d",
            cfg.host,
            cfg.port,
        )
        self._running = True
        try:
            await asyncio.to_thread(self._mcp.run)
        finally:
            self._running = False

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
        self._context = None

    def stop(self) -> None:
        """Signal the server to stop."""
        self._running = False
        logger.info("MCP server stop requested")

    @property
    def is_running(self) -> bool:
        return self._running

    async def capabilities(self) -> dict[str, object]:
        await self.initialize()
        return self._require_context().capabilities.to_dict()

    async def list_resources(self) -> list[ResourceDescriptor]:
        await self.initialize()
        return self._require_resources().list_descriptors()

    async def read_resource(self, uri: str) -> ResourceResult:
        await self.initialize()
        return await self._require_resources().read(uri)

    async def list_tools(
        self, *, tiers: frozenset[int] | None = None
    ) -> list[ToolDescriptor]:
        await self.initialize()
        active_tiers = tiers if tiers is not None else self._tool_tiers
        return self._require_tools().list_descriptors_for_tiers(active_tiers)

    async def call_tool(self, name: str, args: dict[str, Any]) -> ToolResult:
        await self.initialize()
        return await self._require_tools().call(name, args)

    async def list_prompts(self) -> list[dict[str, Any]]:
        await self.initialize()
        return [
            p.model_dump(mode="json") for p in self._require_prompts().list_prompts()
        ]

    async def get_prompt(self, name: str) -> dict[str, Any]:
        await self.initialize()
        return self._require_prompts().get(name)

    async def get_task(self, task_id: str) -> dict[str, Any]:
        """Return the MCP 2025-11-25 ``Task`` object for *task_id* (tasks/get)."""
        await self.initialize()
        task = self._require_tasks().get(task_id)
        return to_protocol_task(task)

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        """Return the payload of a completed task (tasks/result)."""
        await self.initialize()
        return self._require_tasks().result(task_id)

    async def cancel_task(self, task_id: str) -> dict[str, Any]:
        """Cancel a task and return the updated ``Task`` object (tasks/cancel)."""
        await self.initialize()
        task = self._require_tasks().cancel(task_id)
        return to_protocol_task(task)

    async def list_protocol_tasks(self) -> list[dict[str, Any]]:
        """Return all tasks as ``Task`` objects (tasks/list)."""
        await self.initialize()
        return [to_protocol_task(t) for t in self._require_tasks().list_tasks()]

    async def subscribe(self, uri: str) -> None:
        await self.initialize()
        self._require_subscriptions().subscribe(uri)

    def drain_notifications(self) -> list[dict[str, Any]]:
        return self._require_context().notifications.drain()

    def telemetry_events(self) -> list[dict[str, Any]]:
        return self._require_context().telemetry.list_events()

    def _require_context(self) -> McpServerContext:
        if self._context is None:
            raise RuntimeError("MCP server has not been initialized")
        return self._context

    def _require_resources(self) -> ResourceRegistry:
        if self._resources is None:
            raise RuntimeError("MCP server has not been initialized")
        return self._resources

    def _require_tools(self) -> ToolRegistry:
        if self._tools is None:
            raise RuntimeError("MCP server has not been initialized")
        return self._tools

    def _require_prompts(self) -> PromptRegistry:
        if self._prompts is None:
            raise RuntimeError("MCP server has not been initialized")
        return self._prompts

    def _require_subscriptions(self) -> SubscriptionManager:
        if self._subscriptions is None:
            raise RuntimeError("MCP server has not been initialized")
        return self._subscriptions

    def _require_tasks(self) -> TaskManager:
        if self._tasks is None:
            raise RuntimeError("MCP server has not been initialized")
        return self._tasks
