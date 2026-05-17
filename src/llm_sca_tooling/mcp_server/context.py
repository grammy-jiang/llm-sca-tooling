"""Runtime context for the code-intelligence MCP server."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.notifications import NotificationManager
from llm_sca_tooling.mcp_server.sampling import SamplingCapability, detect_sampling
from llm_sca_tooling.mcp_server.telemetry import McpTelemetry
from llm_sca_tooling.memory.store import MemoryStore
from llm_sca_tooling.storage import WorkspaceStore

__all__ = ["McpServerCapabilities", "McpServerContext"]


@dataclass(frozen=True)
class McpServerCapabilities:
    resources: bool
    tools: bool
    prompts: bool
    tasks: bool
    task_cancel: bool
    task_list: bool
    subscriptions: bool
    sampling: SamplingCapability

    def to_dict(self) -> dict[str, object]:
        """Return MCP 2025-11-25 spec-compliant ServerCapabilities.

        Standard capability keys (resources, tools, prompts, tasks) carry
        object values as required by the spec.  ``tasks`` is a first-class
        ServerCapabilities field in 2025-11-25 (it moved out of
        ``experimental``).

        ``sampling`` is a *client* capability; the server tracks it
        internally but must not advertise it in its own capabilities object.
        """
        result: dict[str, object] = {
            "experimental": {},
            "logging": {},
            "prompts": {"listChanged": False},
            "resources": {
                "subscribe": self.subscriptions,
                "listChanged": False,
            },
            "tools": {"listChanged": True},
        }
        if self.tasks:
            task_caps: dict[str, object] = {
                "requests": {"tools": {"call": {}}},
            }
            if self.task_cancel:
                task_caps["cancel"] = {}
            if self.task_list:
                task_caps["list"] = {}
            result["tasks"] = task_caps
        return result


@dataclass
class McpServerContext:
    config: McpServerConfig
    workspace: WorkspaceStore
    notifications: NotificationManager
    telemetry: McpTelemetry
    sampling: SamplingCapability
    memory: MemoryStore = field(default_factory=lambda: MemoryStore("default"))
    # In-process store for implementation-check artifacts (spec, intent-graph,
    # clause-verdict-matrix, trace). Keyed by the full resource URI so handlers
    # can look up with a direct dict.get().
    impl_check_store: dict[str, Any] = field(default_factory=dict)

    @property
    def capabilities(self) -> McpServerCapabilities:
        return McpServerCapabilities(
            resources=True,
            tools=True,
            prompts=True,
            tasks=self.config.enable_tasks,
            task_cancel=self.config.enable_task_cancel,
            task_list=self.config.task_listing_allowed,
            subscriptions=self.config.resource_subscription_enabled,
            sampling=self.sampling,
        )

    @classmethod
    async def create(
        cls,
        config: McpServerConfig,
        *,
        client_capabilities: dict[str, object] | None = None,
    ) -> McpServerContext:
        workspace = await WorkspaceStore.initialize(
            config.workspace_path, in_memory=config.in_memory_workspace
        )
        return cls(
            config=config,
            workspace=workspace,
            notifications=NotificationManager(),
            telemetry=McpTelemetry(enabled=config.telemetry_enabled),
            sampling=detect_sampling(client_capabilities),
        )

    async def close(self) -> None:
        await self.workspace.close()
