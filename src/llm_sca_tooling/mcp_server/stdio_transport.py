"""Stdio JSON-RPC 2.0 transport for the MCP server.

This module implements a line-delimited JSON-RPC 2.0 transport over stdin/stdout
that bridges the MCPServer's ToolRegistry, ResourceRegistry, and PromptRegistry
to external MCP clients (AI agents, Claude Code, Copilot CLI, etc.).

All diagnostic logging is directed to stderr so that stdout carries only
JSON-RPC frames.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import TYPE_CHECKING, Any

from llm_sca_tooling.telemetry.logging import get_logger

if TYPE_CHECKING:
    from llm_sca_tooling.mcp_server.server import MCPServer

__all__ = ["run_stdio"]

logger = get_logger(__name__)

_MCP_PROTOCOL_VERSION = "2025-11-25"

# Supported versions in preference order (newest first).  If a client
# requests an older supported version the server uses it; otherwise the
# server responds with _MCP_PROTOCOL_VERSION and lets the client decide
# whether to disconnect.
_SUPPORTED_VERSIONS = frozenset({"2025-11-25", "2025-03-26", "2024-11-05"})

_SERVER_CAPABILITIES: dict[str, Any] = {
    "experimental": {},
    "logging": {},
    "prompts": {"listChanged": False},
    "resources": {"subscribe": True, "listChanged": True},
    "tasks": {
        "cancel": {},
        "requests": {"tools": {"call": {}}},
    },
    "tools": {"listChanged": True},
}


def _ok(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


async def _handle(server: MCPServer, frame: dict[str, Any]) -> dict[str, Any] | None:
    """Dispatch a single JSON-RPC request to the MCPServer.

    Returns a response dict, or None for notifications (no response expected).
    """
    method: str = frame.get("method", "")
    params: dict[str, Any] = frame.get("params") or {}
    req_id = frame.get("id")

    # Notifications have no id — no response
    if req_id is None:
        return None

    try:
        if method == "initialize":
            # MCP 2025-11-25: capabilities are at params.capabilities (top-level
            # in the request params).  Older clients (pre-2024-11-05) placed them
            # inside params.clientInfo.capabilities — accept that as a fallback.
            client_caps: dict[str, object] = {}
            top_caps = params.get("capabilities") or {}
            if isinstance(top_caps, dict):
                client_caps = top_caps
            # Legacy fallback: some old clients nest capabilities inside clientInfo.
            if not client_caps:
                raw_client_info = params.get("clientInfo") or {}
                if isinstance(raw_client_info, dict):
                    raw_caps = raw_client_info.get("capabilities") or {}
                    if isinstance(raw_caps, dict):
                        client_caps = raw_caps
            await server.initialize(client_capabilities=client_caps or None)
            caps = await server.capabilities()
            # Negotiate protocol version: honour the client's requested version
            # if it is one we support; otherwise fall back to our latest.
            client_version = params.get("protocolVersion", "")
            negotiated_version = (
                client_version
                if client_version in _SUPPORTED_VERSIONS
                else _MCP_PROTOCOL_VERSION
            )
            return _ok(
                req_id,
                {
                    "protocolVersion": negotiated_version,
                    "capabilities": caps if caps else _SERVER_CAPABILITIES,
                    "serverInfo": {
                        "name": server._server_config.server_name,  # noqa: SLF001
                        "version": server._server_config.server_version,  # noqa: SLF001
                    },
                },
            )

        if method == "tools/list":
            await server.initialize()
            tools = await server.list_tools()
            return _ok(
                req_id,
                {
                    "tools": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": t.input_schema,
                        }
                        for t in tools
                    ]
                },
            )

        if method == "tools/call":
            await server.initialize()
            name: str = params.get("name", "")
            args: dict[str, Any] = params.get("arguments") or {}
            result = await server.call_tool(name, args)
            return _ok(
                req_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result.payload),
                        }
                    ],
                    "isError": result.status not in ("completed", "accepted"),
                },
            )

        if method == "resources/list":
            await server.initialize()
            descs = await server.list_resources()
            return _ok(
                req_id,
                {
                    "resources": [
                        {
                            "uri": d.uri_template,
                            "name": d.name,
                            "description": d.description,
                            "mimeType": d.media_type,
                        }
                        for d in descs
                    ]
                },
            )

        if method == "resources/templates/list":
            await server.initialize()
            descs = await server.list_resources()
            templates = [d for d in descs if "{" in d.uri_template]
            return _ok(
                req_id,
                {
                    "resourceTemplates": [
                        {
                            "uriTemplate": d.uri_template,
                            "name": d.name,
                            "description": d.description,
                            "mimeType": d.media_type,
                        }
                        for d in templates
                    ]
                },
            )

        if method == "resources/read":
            await server.initialize()
            uri: str = params.get("uri", "")
            res = await server.read_resource(uri)
            return _ok(
                req_id,
                {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": res.media_type,
                            "text": json.dumps(res.payload),
                        }
                    ]
                },
            )

        if method == "prompts/list":
            await server.initialize()
            prompts = await server.list_prompts()
            return _ok(req_id, {"prompts": prompts})

        if method == "prompts/get":
            await server.initialize()
            name = params.get("name", "")
            prompt = await server.get_prompt(name)
            return _ok(req_id, prompt)

        if method == "ping":
            return _ok(req_id, {})

        # --- Standard task endpoints (MCP 2025-11-25) ---

        if method == "tasks/get":
            await server.initialize()
            task_id: str = params.get("taskId", "")
            task = await server.get_task(task_id)
            return _ok(req_id, task)

        if method == "tasks/result":
            await server.initialize()
            task_id = params.get("taskId", "")
            payload = await server.get_task_result(task_id)
            return _ok(req_id, payload)

        if method == "tasks/cancel":
            await server.initialize()
            task_id = params.get("taskId", "")
            task = await server.cancel_task(task_id)
            return _ok(req_id, task)

        if method == "tasks/list":
            await server.initialize()
            tasks = await server.list_protocol_tasks()
            return _ok(req_id, {"tasks": tasks})

        # Unknown method
        return _err(req_id, -32601, f"Method not found: {method}")

    except Exception as exc:  # noqa: BLE001
        logger.error("error handling %r: %s", method, exc, exc_info=True)
        return _err(req_id, -32603, "Internal error", str(exc))


async def run_stdio(server: MCPServer) -> None:
    """Run the MCP server over stdin/stdout using line-delimited JSON-RPC 2.0.

    Reads one JSON-RPC frame per line from stdin, dispatches to the MCPServer,
    and writes one JSON-RPC response per line to stdout.  All other output
    (logging, diagnostics) goes to stderr.
    """
    loop = asyncio.get_event_loop()
    # 16 MiB limit — default 64 KiB is too small for large spec docs
    reader = asyncio.StreamReader(limit=16 * 1024 * 1024)
    proto = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: proto, sys.stdin)

    writer_transport, writer_proto = await loop.connect_write_pipe(
        asyncio.BaseProtocol, sys.stdout
    )

    def _write(data: bytes) -> None:
        writer_transport.write(data)

    logger.info("stdio transport ready — JSON-RPC on stdin/stdout")

    while True:
        try:
            line = await reader.readline()
        except (asyncio.IncompleteReadError, EOFError):
            break
        if not line:
            break

        raw = line.decode("utf-8", errors="replace").strip()
        if not raw:
            continue

        try:
            frame = json.loads(raw)
        except json.JSONDecodeError as exc:
            resp = _err(None, -32700, f"Parse error: {exc}")
            _write((json.dumps(resp) + "\n").encode())
            continue

        response = await _handle(server, frame)
        if response is not None:
            _write((json.dumps(response) + "\n").encode())
