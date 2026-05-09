"""Minimal indexing CLI."""

from __future__ import annotations

import argparse

from llm_sca_tooling.indexing.service import graph_build, graph_update
from llm_sca_tooling.mcp_server.dev_server import main as mcp_serve_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidence-sca")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("graph-build")
    build.add_argument("repo_path")
    update = sub.add_parser("graph-update")
    update.add_argument("repo_path")
    mcp = sub.add_parser("mcp")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    serve = mcp_sub.add_parser("serve")
    serve.add_argument("--workspace", default=".llm-sca")
    args = parser.parse_args(argv)
    if args.command == "mcp":
        return mcp_serve_main(["--workspace", args.workspace])
    result = graph_build(args.repo_path) if args.command == "graph-build" else graph_update(args.repo_path)
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
