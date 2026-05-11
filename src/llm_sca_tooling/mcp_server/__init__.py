"""MCP server package for the code-intelligence surface."""

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.server import MCPServer

__all__ = ["MCPServer", "McpServerConfig"]
