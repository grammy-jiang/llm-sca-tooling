"""Local code-intelligence server facade."""

from __future__ import annotations

from llm_sca_tooling.mcp_server.capabilities import build_capabilities
from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ServerStartupError
from llm_sca_tooling.mcp_server.notifications import NotificationManager
from llm_sca_tooling.mcp_server.prompt_registry import (
    PromptDescriptor,
    PromptRegistry,
    PromptResult,
)
from llm_sca_tooling.mcp_server.prompts import default_prompt_registry
from llm_sca_tooling.mcp_server.resource_registry import (
    ResourceDescriptor,
    ResourceRegistry,
    ResourceResult,
)
from llm_sca_tooling.mcp_server.resources import default_resource_handlers
from llm_sca_tooling.mcp_server.sampling import detect_sampling
from llm_sca_tooling.mcp_server.subscriptions import Subscription, SubscriptionManager
from llm_sca_tooling.mcp_server.tasks import TaskManager
from llm_sca_tooling.mcp_server.telemetry import TelemetryRecorder
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolRegistry,
    ToolResult,
)
from llm_sca_tooling.mcp_server.tools import default_tool_handlers
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.storage import WorkspaceStore, initialize_workspace


class CodeIntelligenceServer:
    def __init__(
        self,
        config: McpServerConfig | None = None,
        *,
        client_capabilities: JsonObject | None = None,
    ) -> None:
        self.config = config or McpServerConfig()
        self.sampling = detect_sampling(
            self.config.sampling_enabled, client_capabilities
        )
        self.capabilities = build_capabilities(self.config, self.sampling)
        self.workspace: WorkspaceStore | None = None
        self.context: McpRequestContext | None = None
        self.resources = ResourceRegistry()
        self.tools: ToolRegistry | None = None
        self.prompts: PromptRegistry = default_prompt_registry(self.sampling)
        self.notifications = NotificationManager()
        self.subscriptions: SubscriptionManager | None = None
        self.telemetry: TelemetryRecorder | None = None
        self.tasks: TaskManager | None = None
        self.started = False

    def start(self) -> CodeIntelligenceServer:
        self.workspace = initialize_workspace(self.config.workspace_path)
        self.context = McpRequestContext(self.workspace, self.config, self.capabilities)
        for handler in default_resource_handlers():
            self.resources.register(handler)
        self.subscriptions = SubscriptionManager(self.resources)
        self.telemetry = TelemetryRecorder(
            self.workspace, enabled=self.config.telemetry_enabled
        )
        self.tasks = TaskManager(self.workspace, self.config, self.telemetry)
        self.tasks.recover_inflight()
        self.tools = ToolRegistry(
            default_tool_handlers(self.tasks.runner, self.notifications)
        )
        self._startup_checks()
        self.started = True
        return self

    def shutdown(self) -> None:
        if self.workspace:
            self.workspace.close()
        self.started = False

    def health_check(self) -> JsonObject:
        return {
            "status": "ok" if self.started else "stopped",
            "server_name": self.config.server_name,
            "server_version": self.config.server_version,
            "workspace_path": str(self.config.workspace_path),
        }

    def list_resources(self) -> list[ResourceDescriptor]:
        return self.resources.list_descriptors()

    def read_resource(self, uri: str) -> ResourceResult:
        return self.resources.read(self._context(), uri)

    def list_tools(self) -> list[ToolDescriptor]:
        return self._tools().list_descriptors()

    def call_tool(self, name: str, args: JsonObject | None = None) -> ToolResult:
        args = args or {}
        try:
            result = self._tools().call(self._context(), name, args)
            repo_id = (
                result.payload.get("repo_id")
                if isinstance(result.payload.get("repo_id"), str)
                else None
            )
            self._telemetry().record_tool_call(
                name, args, result.status, repo_id=repo_id
            )
            return result
        except Exception as exc:
            self._telemetry().record_tool_call(
                name, args, "failed", error_category=exc.__class__.__name__
            )
            raise

    def list_prompts(self) -> list[PromptDescriptor]:
        return self.prompts.list_descriptors()

    def get_prompt(self, name: str) -> PromptResult:
        return self.prompts.get(name)

    def task_status(self, task_id: str):
        return self._tasks().status(task_id)

    def task_result(self, task_id: str):
        return self._tasks().result(task_id)

    def cancel_task(self, task_id: str):
        return self._tasks().cancel(task_id)

    def list_tasks(self):
        return self._tasks().list()

    def subscribe(self, uri: str) -> Subscription:
        if not self.subscriptions:
            raise ServerStartupError("server not started")
        return self.subscriptions.subscribe(uri)

    def drain_notifications(self):
        return self.notifications.drain()

    def _startup_checks(self) -> None:
        if not (self.config.schema_dir / "graph.schema.json").exists():
            raise ServerStartupError(
                f"missing graph schema: {self.config.schema_dir / 'graph.schema.json'}"
            )
        if not (self.config.schema_dir / "run-record.schema.json").exists():
            raise ServerStartupError(
                f"missing run-record schema: {self.config.schema_dir / 'run-record.schema.json'}"
            )
        required_prompts = {
            "implementation-check",
            "bug-resolve",
            "patch-review",
            "operational-review",
            "readiness-audit",
        }
        names = {prompt.name for prompt in self.prompts.list_descriptors()}
        if names != required_prompts:
            raise ServerStartupError("prompt registry is incomplete")
        if len({tool.name for tool in self._tools().list_descriptors()}) != len(
            self._tools().list_descriptors()
        ):
            raise ServerStartupError("duplicate tool descriptors detected")

    def _context(self) -> McpRequestContext:
        if self.context is None:
            raise ServerStartupError("server not started")
        return self.context

    def _tools(self) -> ToolRegistry:
        if self.tools is None:
            raise ServerStartupError("server not started")
        return self.tools

    def _tasks(self) -> TaskManager:
        if self.tasks is None:
            raise ServerStartupError("server not started")
        return self.tasks

    def _telemetry(self) -> TelemetryRecorder:
        if self.telemetry is None:
            raise ServerStartupError("server not started")
        return self.telemetry


def start(config: McpServerConfig | None = None) -> CodeIntelligenceServer:
    """Start the local code-intelligence server and return the server facade."""

    return CodeIntelligenceServer(config).start()
