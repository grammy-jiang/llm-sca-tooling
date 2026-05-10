"""FastMCP bridge — exposes CodeIntelligenceServer over the standard MCP protocol.

This is the transport layer that Claude Code (and any other MCP client) connects
to.  It does NOT rewrite any tool/resource/prompt logic; it forwards every call
into the existing CodeIntelligenceServer layers that are already tested.

Two deployment scenarios are both handled by the same ``evidence-sca mcp serve``
command:
  - Dev (uv-managed):  ``uv run evidence-sca mcp serve``  (via .mcp.json)
  - Installed package: ``evidence-sca mcp serve``          (via installed entrypoint)
"""

from __future__ import annotations

import json
import logging
from typing import Any

import fastmcp
from fastmcp.prompts.base import PromptArgument
from fastmcp.prompts.function_prompt import FunctionPrompt
from fastmcp.tools import Tool, ToolResult
from mcp.types import TextContent
from pydantic import AnyUrl, ConfigDict

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.prompt_registry import PromptDescriptor
from llm_sca_tooling.mcp_server.serialization import to_jsonable
from llm_sca_tooling.mcp_server.server import CodeIntelligenceServer
from llm_sca_tooling.mcp_server.tool_registry import ToolHandler
from llm_sca_tooling.schemas.base import JsonObject

logger = logging.getLogger(__name__)


class _BridgeTool(Tool):
    """A FastMCP Tool that delegates execution into an existing ToolHandler."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _handler: ToolHandler
    _server: CodeIntelligenceServer
    _mcp: fastmcp.FastMCP

    def _set_backend(
        self,
        handler: ToolHandler,
        server: CodeIntelligenceServer,
        mcp: fastmcp.FastMCP,
    ) -> None:
        object.__setattr__(self, "_handler", handler)
        object.__setattr__(self, "_server", server)
        object.__setattr__(self, "_mcp", mcp)

    async def _forward_notifications(self, notifications: list[JsonObject]) -> None:
        """Forward backend notifications to the connected MCP client session.

        The backend produces Notification dicts in ToolResult.notifications with
        two possible method values:
          - "notifications/resources/updated"  → carries a "uri" key
          - "notifications/resources/list_changed" → no URI, full list changed

        The MCP session exposes:
          - session.send_resource_updated(uri: AnyUrl)
          - session.send_resource_list_changed()

        request_context raises LookupError when called outside a request
        (e.g., in tests or background tasks), so guard with try/except.
        """
        if not notifications:
            return
        try:
            session = self._mcp._mcp_server.request_context.session
        except LookupError:
            logger.debug("No active request context; skipping notification forwarding")
            return

        for notification in notifications:
            method = notification.get("method")
            try:
                if method == "notifications/resources/updated":
                    uri = notification.get("uri")
                    if isinstance(uri, str) and uri:
                        await session.send_resource_updated(AnyUrl(uri))
                elif method == "notifications/resources/list_changed":
                    await session.send_resource_list_changed()
                else:
                    logger.debug("Skipping unknown MCP notification: %s", method)
            except Exception:
                logger.warning(
                    "Failed to forward MCP notification: %s",
                    method,
                    exc_info=True,
                )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        if self._server.context is None:
            raise RuntimeError("server not started")
        backend_result = None
        try:
            backend_result = self._handler.call(self._server.context, arguments)
            text = json.dumps(to_jsonable(backend_result), sort_keys=True)
        except Exception as exc:
            logger.exception("Tool %s failed", self.name)
            text = json.dumps({"error": str(exc)})
        if backend_result is not None and backend_result.notifications:
            await self._forward_notifications(backend_result.notifications)
        return ToolResult(content=[TextContent(type="text", text=text)])


def _read_resource_text(backend: CodeIntelligenceServer, uri: str) -> str:
    try:
        result = backend.read_resource(uri)
        return json.dumps(to_jsonable(result), sort_keys=True)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def build_fastmcp_server(config: McpServerConfig) -> fastmcp.FastMCP:
    """Start CodeIntelligenceServer and return a wired FastMCP instance."""

    backend = CodeIntelligenceServer(config).start()
    mcp = fastmcp.FastMCP(
        "code-intelligence",
        instructions=(
            "Local code-intelligence server for the evidence-sca repository. "
            "Provides graph-backed tools for fault localisation, repo-QA, "
            "blast-radius analysis, patch review, SAST repair, and workflow launchers. "
            "Run 'evidence-sca graph-build <repo>' first to populate the index."
        ),
    )

    # ── Tools ─────────────────────────────────────────────────────────────────
    if backend.tools is None:
        raise RuntimeError("server tools not initialised")
    for descriptor in backend.tools.list_descriptors():
        handler = backend.tools.get(descriptor.name)
        bridge = _BridgeTool(
            name=descriptor.name,
            description=descriptor.description,
            parameters=descriptor.input_schema,
        )
        bridge._set_backend(handler, backend, mcp)
        mcp.add_tool(bridge)
        logger.debug("registered tool: %s", descriptor.name)

    # ── Resources ─────────────────────────────────────────────────────────────
    @mcp.resource("code-intelligence://repos")
    async def list_repos() -> str:
        return _read_resource_text(backend, "code-intelligence://repos")

    @mcp.resource("code-intelligence://interfaces")
    async def list_interfaces() -> str:
        return _read_resource_text(backend, "code-intelligence://interfaces")

    @mcp.resource("code-intelligence://schema/{schema_file}")
    async def get_schema(schema_file: str) -> str:
        return _read_resource_text(backend, f"code-intelligence://schema/{schema_file}")

    @mcp.resource("code-intelligence://graph/{repo}")
    async def get_graph(repo: str) -> str:
        return _read_resource_text(backend, f"code-intelligence://graph/{repo}")

    @mcp.resource("code-intelligence://build-evidence/{repo}")
    async def get_build_evidence(repo: str) -> str:
        return _read_resource_text(
            backend, f"code-intelligence://build-evidence/{repo}"
        )

    @mcp.resource("code-intelligence://sarif/{repo}")
    async def get_sarif_list(repo: str) -> str:
        return _read_resource_text(backend, f"code-intelligence://sarif/{repo}")

    @mcp.resource("code-intelligence://sarif/{repo}/{run_id}")
    async def get_sarif_run(repo: str, run_id: str) -> str:
        return _read_resource_text(
            backend, f"code-intelligence://sarif/{repo}/{run_id}"
        )

    @mcp.resource("code-intelligence://eval/{run_id}")
    async def get_eval_run(run_id: str) -> str:
        return _read_resource_text(backend, f"code-intelligence://eval/{run_id}")

    @mcp.resource("code-intelligence://graph/slice/{repo}/{files}")
    async def get_graph_slice_resource(repo: str, files: str) -> str:
        return _read_resource_text(
            backend, f"code-intelligence://graph/slice/{repo}/{files}"
        )

    @mcp.resource("code-intelligence://summary/{repo}/{symbol_path}")
    async def get_symbol_summary(repo: str, symbol_path: str) -> str:
        return _read_resource_text(
            backend, f"code-intelligence://summary/{repo}/{symbol_path}"
        )

    @mcp.resource("code-intelligence://blame/{repo}/{file_path}")
    async def get_blame(repo: str, file_path: str) -> str:
        return _read_resource_text(
            backend, f"code-intelligence://blame/{repo}/{file_path}"
        )

    @mcp.resource("code-intelligence://memory/{repo}/trajectories")
    async def get_trajectories(repo: str) -> str:
        return _read_resource_text(
            backend, f"code-intelligence://memory/{repo}/trajectories"
        )

    @mcp.resource("code-intelligence://interfaces/{plugin_id}/{interface_name}")
    async def get_interface_detail(plugin_id: str, interface_name: str) -> str:
        return _read_resource_text(
            backend,
            f"code-intelligence://interfaces/{plugin_id}/{interface_name}",
        )

    @mcp.resource("code-intelligence://runs/{run_id}")
    async def get_run_record(run_id: str) -> str:
        return _read_resource_text(backend, f"code-intelligence://runs/{run_id}")

    @mcp.resource("code-intelligence://runs/{run_id}/harness-condition")
    async def get_run_harness_condition(run_id: str) -> str:
        return _read_resource_text(
            backend, f"code-intelligence://runs/{run_id}/harness-condition"
        )

    @mcp.resource("code-intelligence://operations/{repo}/ledger")
    async def get_operations_ledger(repo: str) -> str:
        return _read_resource_text(
            backend, f"code-intelligence://operations/{repo}/ledger"
        )

    @mcp.resource("code-intelligence://governance/{repo}/policy")
    async def get_governance_policy(repo: str) -> str:
        return _read_resource_text(
            backend, f"code-intelligence://governance/{repo}/policy"
        )

    @mcp.resource("code-intelligence://governance/{repo}/manifest-state")
    async def get_governance_manifest_state(repo: str) -> str:
        return _read_resource_text(
            backend, f"code-intelligence://governance/{repo}/manifest-state"
        )

    @mcp.resource("code-intelligence://readiness/{repo}")
    async def get_readiness(repo: str) -> str:
        return _read_resource_text(backend, f"code-intelligence://readiness/{repo}")

    @mcp.resource("code-intelligence://incidents/{incident_id}")
    async def get_incident(incident_id: str) -> str:
        return _read_resource_text(
            backend, f"code-intelligence://incidents/{incident_id}"
        )

    # ── Prompts ───────────────────────────────────────────────────────────────
    for pdesc in backend.prompts.list_descriptors():
        _register_prompt(mcp, backend, pdesc)

    return mcp


def _register_prompt(
    mcp: fastmcp.FastMCP,
    backend: CodeIntelligenceServer,
    pdesc: PromptDescriptor,
) -> None:
    name = pdesc.name

    async def _prompt() -> str:
        try:
            result = backend.get_prompt(name)
            return json.dumps(to_jsonable(result), sort_keys=True)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    mcp.add_prompt(
        FunctionPrompt(
            name=name,
            description=pdesc.description,
            arguments=_prompt_arguments(pdesc),
            meta={"inputSchema": pdesc.arguments_schema},
            fn=_prompt,
        )
    )
    logger.debug("registered prompt: %s", name)


def _prompt_arguments(pdesc: PromptDescriptor) -> list[PromptArgument]:
    properties = pdesc.arguments_schema.get("properties", {})
    required = set(pdesc.arguments_schema.get("required", []))
    if not isinstance(properties, dict):
        return []
    return [
        PromptArgument(name=name, required=name in required)
        for name in sorted(properties)
    ]
