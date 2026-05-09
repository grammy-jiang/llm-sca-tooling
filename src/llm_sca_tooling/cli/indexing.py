"""Minimal indexing CLI."""

from __future__ import annotations

import argparse

from llm_sca_tooling.indexing.service import graph_build, graph_update


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidence-sca")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("graph-build")
    build.add_argument("repo_path")
    update = sub.add_parser("graph-update")
    update.add_argument("repo_path")
    args = parser.parse_args(argv)
    result = graph_build(args.repo_path) if args.command == "graph-build" else graph_update(args.repo_path)
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
