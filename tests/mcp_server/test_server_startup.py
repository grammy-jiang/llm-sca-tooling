from __future__ import annotations

import pytest

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.resource_registry import ResourceRegistry
from llm_sca_tooling.mcp_server.resources.core import ReposResource
from llm_sca_tooling.mcp_server.server import CodeIntelligenceServer
from llm_sca_tooling.mcp_server.tool_registry import ToolRegistry
from llm_sca_tooling.mcp_server.tools.core import PluginReloadTool


def test_server_starts_and_reports_capabilities(mcp_server) -> None:
    assert mcp_server.capabilities.server_name == "code-intelligence"
    assert mcp_server.capabilities.resources
    assert mcp_server.workspace is not None


def test_missing_schema_fails_startup(tmp_path) -> None:
    config = McpServerConfig(workspace_path=tmp_path / "ws", schema_dir=tmp_path / "missing")
    with pytest.raises(Exception, match="missing graph schema"):
        CodeIntelligenceServer(config).start()


def test_duplicate_registry_entries_fail() -> None:
    resources = ResourceRegistry([ReposResource()])
    with pytest.raises(Exception, match="duplicate resource"):
        resources.register(ReposResource())
    tools = ToolRegistry([PluginReloadTool()])
    with pytest.raises(Exception, match="duplicate tool"):
        tools.register(PluginReloadTool())
