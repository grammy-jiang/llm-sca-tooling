"""JSON-lines development server for the local MCP facade."""

from __future__ import annotations

import argparse
import json
import sys

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.errors import McpServerError
from llm_sca_tooling.mcp_server.serialization import to_jsonable
from llm_sca_tooling.mcp_server.server import CodeIntelligenceServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidence-sca mcp serve")
    parser.add_argument("--workspace", default=".llm-sca")
    args = parser.parse_args(argv)
    server = CodeIntelligenceServer(McpServerConfig.for_workspace(args.workspace)).start()
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            request = json.loads(line)
            response = _dispatch(server, request)
            print(json.dumps(to_jsonable(response), sort_keys=True), flush=True)
    finally:
        server.shutdown()
    return 0


def _dispatch(server: CodeIntelligenceServer, request: dict):
    try:
        method = request.get("method")
        params = request.get("params") or {}
        if method == "resources/list":
            return server.list_resources()
        if method == "resources/read":
            return server.read_resource(params["uri"])
        if method == "tools/list":
            return server.list_tools()
        if method == "tools/call":
            return server.call_tool(params["name"], params.get("args") or {})
        if method == "prompts/list":
            return server.list_prompts()
        if method == "prompts/get":
            return server.get_prompt(params["name"])
        if method == "tasks/status":
            return server.task_status(params["task_id"])
        if method == "tasks/result":
            return server.task_result(params["task_id"])
        raise McpServerError(f"unknown method: {method}")
    except McpServerError as exc:
        return {"error": exc.to_payload()}


if __name__ == "__main__":
    raise SystemExit(main())
