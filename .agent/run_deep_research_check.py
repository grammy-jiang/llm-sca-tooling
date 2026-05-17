#!/usr/bin/env python3
"""Compliance check: research-pipeline vs deep-research architecture design doc.

Focuses on v1 scope (P0+P1+P2) from deep-research-system-architecture-design.md.
"""

import json
import subprocess
import sys
import time
from pathlib import Path


def send_recv(proc: subprocess.Popen, msg: dict) -> dict:
    """Send a JSON-RPC message and receive response."""
    line = json.dumps(msg) + "\n"
    proc.stdin.write(line.encode())
    proc.stdin.flush()
    response_line = proc.stdout.readline()
    return json.loads(response_line)


def poll_task(
    proc: subprocess.Popen, task_id: str, msg_id: int, max_wait: int = 300
) -> dict:
    """Poll a task until it completes."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        resp = send_recv(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "task_status", "arguments": {"task_id": task_id}},
                "id": msg_id,
            },
        )
        payload = resp.get("result", {})
        status = payload.get("status") or (
            payload.get("content", [{}])[0].get("text", "{}")
        )
        if isinstance(status, str):
            try:
                status_data = json.loads(status)
                status = status_data.get("status", "unknown")
            except Exception:
                pass
        print(f"  Task {task_id}: status={status}", file=sys.stderr)
        if status == "completed":
            return resp
        if status in ("failed", "error"):
            return resp
        time.sleep(5)
        msg_id += 1
    return {"error": "timeout"}


def main():
    repo_path = "/home/grammy-jiang/projects/research-pipeline"
    artifacts_dir = Path("/home/grammy-jiang/Documents/evidence-sca/.agent/artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Read deep-research architecture doc as spec
    deep_research_arch = Path(
        "/home/grammy-jiang/Documents/Research/deep-research/"
        "deep-research-system-architecture-design.md"
    )
    spec_text = deep_research_arch.read_text()

    print("Starting llm-sca-tooling MCP server...", file=sys.stderr)
    proc = subprocess.Popen(
        ["uv", "run", "llm-sca-tooling", "mcp", "serve", "--transport", "stdio"],
        cwd="/home/grammy-jiang/Documents/evidence-sca",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
    )

    try:
        # Step 1: Initialize
        print("Step 1: Initializing...", file=sys.stderr)
        init_resp = send_recv(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "agent", "version": "1"},
                },
                "id": 1,
            },
        )
        print(f"Init ok: {bool(init_resp.get('result'))}", file=sys.stderr)

        # Step 2: Register repository
        print("\nStep 2: Registering repository...", file=sys.stderr)
        reg_resp = send_recv(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "register_repo",
                    "arguments": {"repo_path": repo_path},
                },
                "id": 2,
            },
        )
        reg_content = reg_resp.get("result", {}).get("content", [{}])
        reg_text = reg_content[0].get("text", "{}") if reg_content else "{}"
        reg_data = json.loads(reg_text) if isinstance(reg_text, str) else reg_text
        repo_id = None
        if isinstance(reg_data, dict):
            repo_id = (
                reg_data.get("payload", {}).get("repo", {}).get("repo_id")
                or reg_data.get("repo_id")
                or reg_data.get("id")
            )
        print(f"  repo_id: {repo_id}", file=sys.stderr)

        # Step 3: Build graph (may use cached)
        print("\nStep 3: Building graph index...", file=sys.stderr)
        graph_args = {"repo_id": repo_id} if repo_id else {"repo_path": repo_path}
        build_resp = send_recv(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "graph_build", "arguments": graph_args},
                "id": 3,
            },
        )
        build_content = build_resp.get("result", {}).get("content", [{}])
        build_text = build_content[0].get("text", "{}") if build_content else "{}"
        build_data = (
            json.loads(build_text) if isinstance(build_text, str) else build_text
        )
        task_id = None
        if isinstance(build_data, dict):
            task_id = build_data.get("task_id") or build_data.get("id")
            status = build_data.get("status", "")
            if status == "accepted" and task_id:
                print(f"  Async task_id: {task_id}, polling...", file=sys.stderr)
                poll_task(proc, task_id, 4)
                send_recv(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {
                            "name": "task_result",
                            "arguments": {"task_id": task_id},
                        },
                        "id": 10,
                    },
                )
            elif task_id and status not in ("accepted",):
                print(f"  Graph build: {build_data}", file=sys.stderr)

        # Step 4: Run implementation check against deep-research architecture doc
        print(
            "\nStep 4: Running implementation check vs deep-research architecture...",
            file=sys.stderr,
        )
        impl_args = {"spec": spec_text}
        if repo_id:
            impl_args["repo"] = repo_id
        impl_resp = send_recv(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "run_implementation_check", "arguments": impl_args},
                "id": 20,
            },
        )
        (artifacts_dir / "deep_research_impl_check.json").write_text(
            json.dumps(impl_resp, indent=2)
        )

        # Parse results
        impl_content = impl_resp.get("result", {}).get("content", [{}])
        impl_text = impl_content[0].get("text", "{}") if impl_content else "{}"
        impl_data = json.loads(impl_text) if isinstance(impl_text, str) else impl_text

        violated = []
        unknown = []
        satisfied = []
        verdict = "unknown"
        if isinstance(impl_data, dict):
            report = impl_data.get("report", impl_data)
            violated = report.get("violated_clauses", [])
            unknown = report.get("unknown_clauses", [])
            satisfied = report.get("satisfied_clauses", [])
            verdict = report.get("overall_verdict", "unknown")

        print(f"\n  Verdict: {verdict}", file=sys.stderr)
        print(f"  Satisfied clauses: {len(satisfied)}", file=sys.stderr)
        print(f"  Violated clauses: {len(violated)}", file=sys.stderr)
        print(f"  Unknown clauses: {len(unknown)}", file=sys.stderr)

        # Investigate violated clauses
        for i, clause in enumerate(violated[:5]):
            clause_text = (
                clause.get("text", str(clause))
                if isinstance(clause, dict)
                else str(clause)
            )
            clause_id = (
                clause.get("id", f"clause_{i}")
                if isinstance(clause, dict)
                else f"clause_{i}"
            )
            print(f"\n  VIOLATED: {clause_id}: {clause_text[:150]}", file=sys.stderr)

        # Write summary
        summary = {
            "spec": "deep-research-system-architecture-design.md",
            "repo": repo_path,
            "verdict": verdict,
            "satisfied_count": len(satisfied),
            "violated_count": len(violated),
            "unknown_count": len(unknown),
            "violated_clauses": violated[:20],
            "unknown_clauses": unknown[:20],
        }
        (artifacts_dir / "deep_research_compliance_summary.json").write_text(
            json.dumps(summary, indent=2)
        )

        # Write markdown report
        report_lines = [
            "# Deep-Research Architecture Compliance Report",
            "",
            f"**Spec**: `deep-research-system-architecture-design.md`",
            f"**Repo**: `{repo_path}`",
            f"**Verdict**: `{verdict}`",
            "",
            "## Results",
            f"- Satisfied clauses: {len(satisfied)}",
            f"- Violated clauses: {len(violated)}",
            f"- Unknown clauses: {len(unknown)}",
            "",
        ]
        if violated:
            report_lines.append("## Violated Clauses")
            for c in violated:
                cid = c.get("id", "?") if isinstance(c, dict) else "?"
                ctxt = c.get("text", str(c)) if isinstance(c, dict) else str(c)
                report_lines.append(f"- **{cid}**: {ctxt[:200]}")
            report_lines.append("")
        if unknown:
            report_lines.append("## Unknown Clauses (runtime-behavioral or ambiguous)")
            for c in unknown:
                cid = c.get("id", "?") if isinstance(c, dict) else "?"
                ctxt = c.get("text", str(c)) if isinstance(c, dict) else str(c)
                report_lines.append(f"- **{cid}**: {ctxt[:200]}")
            report_lines.append("")
        (artifacts_dir / "deep_research_compliance_report.md").write_text(
            "\n".join(report_lines)
        )
        print(
            f"\nReport written to: {artifacts_dir}/deep_research_compliance_report.md",
            file=sys.stderr,
        )

    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
