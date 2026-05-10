from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.mcp_server import CodeIntelligenceServer, McpServerConfig


@pytest.fixture
def mcp_server(tmp_path: Path):
    server = CodeIntelligenceServer(
        McpServerConfig.for_workspace(tmp_path / "workspace")
    ).start()
    yield server
    server.shutdown()
