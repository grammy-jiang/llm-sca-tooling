"""MCP stdio server entrypoint.

Starts the FastMCP bridge which speaks the standard MCP protocol, enabling
Claude Code, GitHub Copilot, and Codex CLI to connect via .mcp.json config.

Two deployment scenarios both use the same command:
  dev (uv):   uv run evidence-sca mcp serve   (runs local editable install)
  installed:  evidence-sca mcp serve           (runs installed package)
"""

from __future__ import annotations

import argparse

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.fastmcp_bridge import build_fastmcp_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidence-sca mcp serve")
    parser.add_argument("--workspace", default=".llm-sca")
    args = parser.parse_args(argv)

    config = McpServerConfig.for_workspace(args.workspace)
    mcp = build_fastmcp_server(config)
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
