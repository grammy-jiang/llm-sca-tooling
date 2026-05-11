"""Tests for the placeholder MCP server."""

from __future__ import annotations

import pytest

from llm_sca_tooling.config import MCPConfig
from llm_sca_tooling.mcp_server.server import MCPServer


@pytest.fixture()
def server() -> MCPServer:
    return MCPServer(MCPConfig(host="127.0.0.1", port=9999, dev_mode=True))


def test_server_instantiation(server: MCPServer) -> None:
    assert server is not None


def test_server_not_running_by_default(server: MCPServer) -> None:
    assert server.is_running is False


def test_server_stop_when_not_running(server: MCPServer) -> None:
    server.stop()
    assert server.is_running is False


def test_server_default_config() -> None:
    s = MCPServer()
    assert s is not None
    assert s.is_running is False


def test_server_config_stored() -> None:
    cfg = MCPConfig(host="127.0.0.1", port=8080, dev_mode=False)
    s = MCPServer(cfg)
    assert s._config.port == 8080


def test_server_start_sets_running_and_resets(monkeypatch, server: MCPServer) -> None:
    observed = []

    def fake_run() -> None:
        observed.append(server.is_running)

    monkeypatch.setattr(server._mcp, "run", fake_run)
    server.start()
    assert observed == [True]
    assert server.is_running is False


async def test_server_start_async_sets_running_and_resets(
    monkeypatch, server: MCPServer
) -> None:
    observed = []

    def fake_run() -> None:
        observed.append(server.is_running)

    monkeypatch.setattr(server._mcp, "run", fake_run)
    await server.start_async()
    assert observed == [True]
    assert server.is_running is False


def test_server_start_resets_after_error(monkeypatch, server: MCPServer) -> None:
    def fake_run() -> None:
        raise RuntimeError("server failed")

    monkeypatch.setattr(server._mcp, "run", fake_run)
    with pytest.raises(RuntimeError, match="server failed"):
        server.start()
    assert server.is_running is False
