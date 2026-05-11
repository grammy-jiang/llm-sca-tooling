"""Runtime context for the code-intelligence MCP server."""

from __future__ import annotations

from dataclasses import dataclass, field

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
    subscriptions: bool
    sampling: SamplingCapability

    def to_dict(self) -> dict[str, object]:
        return {
            "resources": self.resources,
            "tools": self.tools,
            "prompts": self.prompts,
            "tasks": self.tasks,
            "subscriptions": self.subscriptions,
            "sampling": self.sampling.model_dump(mode="json"),
        }


@dataclass
class McpServerContext:
    config: McpServerConfig
    workspace: WorkspaceStore
    notifications: NotificationManager
    telemetry: McpTelemetry
    sampling: SamplingCapability
    memory: MemoryStore = field(default_factory=lambda: MemoryStore("default"))

    @property
    def capabilities(self) -> McpServerCapabilities:
        return McpServerCapabilities(
            resources=True,
            tools=True,
            prompts=True,
            tasks=self.config.enable_tasks,
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
