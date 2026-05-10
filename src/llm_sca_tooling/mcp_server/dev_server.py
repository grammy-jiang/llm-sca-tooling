"""MCP stdio server entrypoint.

Starts the FastMCP bridge which speaks the standard MCP protocol, enabling
Claude Code, GitHub Copilot, and Codex CLI to connect via .mcp.json config.

Two deployment scenarios both use the same command:
  dev (uv):   uv run evidence-sca mcp serve   (runs local editable install)
  installed:  evidence-sca mcp serve           (runs installed package)
"""

from __future__ import annotations

import argparse
import logging
import sys

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.fastmcp_bridge import build_fastmcp_server
from llm_sca_tooling.mcp_server.stdio_compat import install_threaded_stdio_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidence-sca mcp serve")
    parser.add_argument("--workspace", default=".llm-sca")
    args = parser.parse_args(argv)

    config = McpServerConfig.for_workspace(args.workspace)
    mcp = build_fastmcp_server(config)
    install_threaded_stdio_server()
    _configure_stdio_logging()
    mcp.run(transport="stdio", show_banner=False, log_level="ERROR")
    return 0


def _configure_stdio_logging() -> None:
    """Keep stdio stdout reserved for JSON-RPC protocol messages."""

    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.ERROR)
    root.addHandler(handler)
    root.setLevel(logging.ERROR)
    logging.getLogger("mcp").setLevel(logging.ERROR)
    logging.getLogger("fastmcp").setLevel(logging.ERROR)


if __name__ == "__main__":
    raise SystemExit(main())
