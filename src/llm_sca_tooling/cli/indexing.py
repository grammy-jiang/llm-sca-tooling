"""Minimal indexing CLI."""

from __future__ import annotations

import argparse

from llm_sca_tooling import __version__
from llm_sca_tooling.indexing.service import graph_build, graph_update
from llm_sca_tooling.mcp_server.dev_server import main as mcp_serve_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidence-sca")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")
    build = sub.add_parser("graph-build")
    build.add_argument("repo_path")
    update = sub.add_parser("graph-update")
    update.add_argument("repo_path")
    mcp = sub.add_parser("mcp")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    serve = mcp_sub.add_parser("serve")
    serve.add_argument("--workspace", default=".llm-sca")
    setup_p = sub.add_parser(
        "setup",
        help=(
            "Detect local AI agents (Claude Code, GitHub Copilot, Codex CLI) "
            "and configure MCP server and skills for each."
        ),
    )
    setup_p.add_argument(
        "--workspace",
        default=".llm-sca",
        help="evidence-sca workspace path (passed to 'mcp serve'). Default: .llm-sca",
    )
    setup_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be configured without writing files.",
    )
    setup_p.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.version:
        print(f"evidence-sca {__version__}")
        return 0
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == "setup":
        from llm_sca_tooling.cli.setup_cmd import print_results, run_setup

        results = run_setup(workspace=args.workspace, dry_run=args.dry_run)
        print_results(results, verbose=args.verbose)
        return 1 if any(r.errors for r in results) else 0
    if args.command == "mcp":
        return mcp_serve_main(["--workspace", args.workspace])
    result = (
        graph_build(args.repo_path)
        if args.command == "graph-build"
        else graph_update(args.repo_path)
    )
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
