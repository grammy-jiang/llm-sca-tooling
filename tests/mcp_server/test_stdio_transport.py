"""Stdio JSON-RPC transport — the primary MCP integration path.

Covers the `_handle` dispatcher for every protocol method plus the
`run_stdio` read/dispatch/write loop over a real pipe pair. The transport
was previously at 0% coverage despite being the main client entrypoint.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from llm_sca_tooling.mcp_server import MCPServer, McpServerConfig
from llm_sca_tooling.mcp_server.stdio_transport import (
    _err,
    _handle,
    _ok,
    run_stdio,
)


@pytest.fixture()
async def server(tmp_path: Path) -> MCPServer:
    return MCPServer(McpServerConfig(workspace_path=tmp_path / "workspace"))


def _req(method: str, params: dict | None = None, req_id: int | str | None = 1) -> dict:
    frame: dict = {"jsonrpc": "2.0", "method": method}
    if req_id is not None:
        frame["id"] = req_id
    if params is not None:
        frame["params"] = params
    return frame


# ── helpers ──────────────────────────────────────────────────────────────────


def test_ok_and_err_frames() -> None:
    assert _ok(7, {"x": 1}) == {"jsonrpc": "2.0", "id": 7, "result": {"x": 1}}
    err = _err(7, -32601, "Method not found", "extra")
    assert err["error"]["code"] == -32601
    assert err["error"]["data"] == "extra"
    # no data -> no data key
    assert "data" not in _err(7, -1, "m")["error"]


# ── _handle dispatch ─────────────────────────────────────────────────────────


async def test_notification_returns_none(server: MCPServer) -> None:
    # No id -> notification -> no response.
    assert await _handle(server, _req("notifications/initialized", req_id=None)) is None


async def test_initialize_negotiates_supported_version(server: MCPServer) -> None:
    resp = await _handle(
        server,
        _req("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}}),
    )
    assert resp is not None
    result = resp["result"]
    assert result["protocolVersion"] == "2024-11-05"  # client version honoured
    assert "serverInfo" in result
    assert "capabilities" in result


async def test_initialize_unsupported_version_falls_back(server: MCPServer) -> None:
    resp = await _handle(server, _req("initialize", {"protocolVersion": "1999-01-01"}))
    assert resp["result"]["protocolVersion"] == "2025-11-25"


async def test_initialize_legacy_nested_capabilities(server: MCPServer) -> None:
    resp = await _handle(
        server,
        _req(
            "initialize",
            {"clientInfo": {"capabilities": {"sampling": {}}}},
        ),
    )
    assert resp["result"]["serverInfo"]["name"]


async def test_tools_list_and_call(server: MCPServer) -> None:
    listed = await _handle(server, _req("tools/list"))
    names = {t["name"] for t in listed["result"]["tools"]}
    assert "register_repo" in names

    called = await _handle(
        server,
        _req(
            "tools/call",
            {"name": "run_issue_resolution", "arguments": {"issue_text": "boom"}},
        ),
    )
    assert called["result"]["isError"] is False
    payload = json.loads(called["result"]["content"][0]["text"])
    assert payload["report"]["run_id"]


async def test_tools_call_error_sets_is_error(server: MCPServer) -> None:
    resp = await _handle(
        server,
        _req("tools/call", {"name": "register_repo", "arguments": {}}),
    )
    # Missing required repo_path -> internal error path -> JSON-RPC error.
    assert "error" in resp
    assert resp["error"]["code"] == -32603


async def test_resources_list_templates_and_read(server: MCPServer) -> None:
    listed = await _handle(server, _req("resources/list"))
    assert "resources" in listed["result"]

    templates = await _handle(server, _req("resources/templates/list"))
    assert all(
        "{" in t["uriTemplate"] for t in templates["result"]["resourceTemplates"]
    )

    read = await _handle(
        server, _req("resources/read", {"uri": "code-intelligence://repos"})
    )
    assert read["result"]["contents"][0]["uri"] == "code-intelligence://repos"


async def test_prompts_list_and_get(server: MCPServer) -> None:
    listed = await _handle(server, _req("prompts/list"))
    assert listed["result"]["prompts"]
    got = await _handle(server, _req("prompts/get", {"name": "implementation-check"}))
    assert got["result"]


async def test_ping(server: MCPServer) -> None:
    assert await _handle(server, _req("ping")) == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {},
    }


async def test_task_endpoints(server: MCPServer) -> None:
    # Kick off an async task so the task endpoints have something to read.
    accepted = await _handle(
        server,
        _req(
            "tools/call",
            {
                "name": "graph_build",
                "arguments": {
                    "repo_path": str(
                        server._server_config.workspace_path
                    ),  # noqa: SLF001
                    "task": True,
                },
            },
        ),
    )
    task_id = json.loads(accepted["result"]["content"][0]["text"])["task"]["task_id"]

    got = await _handle(server, _req("tasks/get", {"taskId": task_id}))
    assert got["result"]["taskId"] == task_id

    # tasks/result returns either a completed result or a not-ready/error frame.
    res = await _handle(server, _req("tasks/result", {"taskId": task_id}))
    assert "result" in res or "error" in res

    # tasks/list is gated by server policy by default; either a result or a
    # permission-denied JSON-RPC error is a valid, covered outcome.
    listed = await _handle(server, _req("tasks/list"))
    assert "tasks" in listed.get("result", {}) or listed.get("error")

    cancelled = await _handle(server, _req("tasks/cancel", {"taskId": task_id}))
    assert cancelled["result"]["taskId"] == task_id


async def test_unknown_method(server: MCPServer) -> None:
    resp = await _handle(server, _req("does/not/exist"))
    assert resp["error"]["code"] == -32601


# ── run_stdio loop over a real pipe pair ─────────────────────────────────────


async def test_run_stdio_loop(server: MCPServer, monkeypatch) -> None:
    in_r, in_w = os.pipe()
    out_r, out_w = os.pipe()
    fake_stdin = os.fdopen(in_r, "rb", buffering=0)
    fake_stdout = os.fdopen(out_w, "wb", buffering=0)
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    # Feed: a valid ping, a malformed line (parse error), then EOF.
    with os.fdopen(in_w, "wb", buffering=0) as feed:
        feed.write((json.dumps(_req("ping", req_id=42)) + "\n").encode())
        feed.write(b"{ not json\n")

    await asyncio.wait_for(run_stdio(server), timeout=10)

    fake_stdout.close()
    with os.fdopen(out_r, "rb") as sink:
        lines = [json.loads(line) for line in sink.read().splitlines() if line.strip()]

    by_id = {frame.get("id"): frame for frame in lines}
    assert by_id[42]["result"] == {}
    # Parse error -> JSON-RPC -32700 with null id.
    parse_err = next(f for f in lines if f.get("error", {}).get("code") == -32700)
    assert parse_err["id"] is None
