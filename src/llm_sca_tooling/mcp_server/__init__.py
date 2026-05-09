"""Local code-intelligence MCP server core."""

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.server import CodeIntelligenceServer

__all__ = ["CodeIntelligenceServer", "McpServerConfig"]
