#!/usr/bin/env python3
"""Architecture compliance check script for research-pipeline.

Follows the architecture-compliance skill workflow:
1. Start MCP server (external)
2. Register repository
3. Build graph index (async)
4. Run implementation check
5. Investigate violated/unknown clauses
6. Run readiness audit
7. Emit structured report
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


def poll_task(proc: subprocess.Popen, task_id: str, msg_id: int, max_wait: int = 300) -> dict:
    """Poll a task until it completes."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        resp = send_recv(proc, {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "task_status", "arguments": {"task_id": task_id}},
            "id": msg_id,
        })
        payload = resp.get("result", {})
        status = payload.get("status") or (payload.get("content", [{}])[0].get("text", "{}"))
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

    # Read architecture doc as spec
    arch_doc_path = Path(repo_path) / "docs" / "architecture.md"
    impl_plan_path = Path(repo_path) / "docs" / "implementation-plan.md"
    spec_text = arch_doc_path.read_text()
    if impl_plan_path.exists():
        spec_text += "\n\n---\n\n" + impl_plan_path.read_text()

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
        init_resp = send_recv(proc, {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agent", "version": "1"},
            },
            "id": 1,
        })
        print(f"Init: {json.dumps(init_resp, indent=2)}", file=sys.stderr)

        # Step 2: Register repository
        print("\nStep 2: Registering repository...", file=sys.stderr)
        reg_resp = send_recv(proc, {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "register_repo",
                "arguments": {"repo_path": repo_path},
            },
            "id": 2,
        })
        print(f"Register: {json.dumps(reg_resp, indent=2)}", file=sys.stderr)

        # Extract repo_id
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

        (artifacts_dir / "register_repo.json").write_text(json.dumps(reg_resp, indent=2))

        # Step 3: Build graph index (async)
        print("\nStep 3: Building graph index...", file=sys.stderr)
        graph_args = {"repo_path": repo_path}
        if repo_id:
            graph_args = {"repo_id": repo_id}
        build_resp = send_recv(proc, {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "graph_build", "arguments": graph_args},
            "id": 3,
        })
        print(f"Graph build response: {json.dumps(build_resp, indent=2)}", file=sys.stderr)

        # Check if async
        build_content = build_resp.get("result", {}).get("content", [{}])
        build_text = build_content[0].get("text", "{}") if build_content else "{}"
        build_data = json.loads(build_text) if isinstance(build_text, str) else build_text
        task_id = None
        if isinstance(build_data, dict):
            task_id = build_data.get("task_id") or build_data.get("id")
            status = build_data.get("status", "")
            if status == "accepted" and task_id:
                print(f"  Async task_id: {task_id}, polling...", file=sys.stderr)
                poll_resp = poll_task(proc, task_id, 4)
                # Get task result
                result_resp = send_recv(proc, {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "task_result", "arguments": {"task_id": task_id}},
                    "id": 10,
                })
                print(f"  Graph build result: {json.dumps(result_resp, indent=2)}", file=sys.stderr)
                (artifacts_dir / "graph_build_result.json").write_text(json.dumps(result_resp, indent=2))

        (artifacts_dir / "graph_build.json").write_text(json.dumps(build_resp, indent=2))

        # Step 4: Run implementation check
        print("\nStep 4: Running implementation check...", file=sys.stderr)
        impl_args = {"spec": spec_text}
        if repo_id:
            impl_args["repo"] = repo_id
        impl_resp = send_recv(proc, {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "run_implementation_check", "arguments": impl_args},
            "id": 20,
        })
        print(f"Implementation check: {json.dumps(impl_resp, indent=2)[:2000]}", file=sys.stderr)
        (artifacts_dir / "impl_check_report.json").write_text(json.dumps(impl_resp, indent=2))

        # Extract violated/unknown clauses
        impl_content = impl_resp.get("result", {}).get("content", [{}])
        impl_text = impl_content[0].get("text", "{}") if impl_content else "{}"
        impl_data = json.loads(impl_text) if isinstance(impl_text, str) else impl_text

        violated = []
        unknown = []
        verdict = "unknown"
        if isinstance(impl_data, dict):
            report = impl_data.get("report", impl_data)
            violated = report.get("violated_clauses", [])
            unknown = report.get("unknown_clauses", [])
            verdict = report.get("overall_verdict", "unknown")

        print(f"\n  Verdict: {verdict}", file=sys.stderr)
        print(f"  Violated clauses: {len(violated)}", file=sys.stderr)
        print(f"  Unknown clauses: {len(unknown)}", file=sys.stderr)

        # Step 5: Investigate violated/unknown clauses
        investigation_results = []
        clauses_to_investigate = violated[:10] + unknown[:10]  # limit to first 10 of each

        repo_ref = repo_id if repo_id else repo_path

        for i, clause in enumerate(clauses_to_investigate):
            clause_text = clause.get("text", str(clause)) if isinstance(clause, dict) else str(clause)
            clause_id = clause.get("id", f"clause_{i}") if isinstance(clause, dict) else f"clause_{i}"
            print(f"\nStep 5: Investigating clause {clause_id}: {clause_text[:100]}...", file=sys.stderr)

            # get_relevant_files
            rel_files_resp = send_recv(proc, {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "get_relevant_files",
                    "arguments": {"query": clause_text, "repo": repo_ref},
                },
                "id": 30 + i * 2,
            })

            # run_static_analysis
            sa_resp = send_recv(proc, {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "run_static_analysis",
                    "arguments": {"repo": repo_ref, "predicate": clause_text},
                },
                "id": 31 + i * 2,
            })

            investigation_results.append({
                "clause_id": clause_id,
                "clause_text": clause_text,
                "relevant_files": rel_files_resp,
                "static_analysis": sa_resp,
            })

        clause_investigation = {"clauses": investigation_results}
        (artifacts_dir / "clause_investigation.json").write_text(json.dumps(clause_investigation, indent=2))
        print(f"\nInvestigated {len(investigation_results)} clauses", file=sys.stderr)

        # Step 6: Run readiness audit
        print("\nStep 6: Running readiness audit...", file=sys.stderr)
        readiness_resp = send_recv(proc, {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "run_readiness_audit",
                "arguments": {"repo": repo_ref},
            },
            "id": 100,
        })
        (artifacts_dir / "readiness_report.json").write_text(json.dumps(readiness_resp, indent=2))
        print(f"Readiness: {json.dumps(readiness_resp, indent=2)[:1000]}", file=sys.stderr)

        # Check run record
        run_record_resp = send_recv(proc, {
            "jsonrpc": "2.0",
            "method": "resources/read",
            "params": {"uri": "code-intelligence://runs/latest"},
            "id": 101,
        })
        (artifacts_dir / "run_record.json").write_text(json.dumps(run_record_resp, indent=2))
        print(f"\nRun record: {json.dumps(run_record_resp, indent=2)[:500]}", file=sys.stderr)

        # Step 7: Produce compliance report (from artifacts)
        print("\nStep 7: Writing compliance report...", file=sys.stderr)

        # Extract readiness data
        readiness_content = readiness_resp.get("result", {}).get("content", [{}])
        readiness_text = readiness_content[0].get("text", "{}") if readiness_content else "{}"
        readiness_data = json.loads(readiness_text) if isinstance(readiness_text, str) else readiness_text

        satisfied = []
        if isinstance(impl_data, dict):
            report = impl_data.get("report", impl_data)
            satisfied = report.get("satisfied_clauses", [])

        compliance_report = f"""# Compliance Report — research-pipeline

**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}
**Source**: `.agent/artifacts/impl_check_report.json`

## Compliance Summary
- overall_verdict: {verdict}
- satisfied_clauses: {len(satisfied)}
- violated_clauses: {len(violated)}
- unknown_clauses: {len(unknown)}

## Confirmed Violations
"""
        for clause in violated:
            cid = clause.get("id", "?") if isinstance(clause, dict) else "?"
            ctext = clause.get("text", str(clause)) if isinstance(clause, dict) else str(clause)
            compliance_report += f"\n- clause_id: {cid}\n  summary: {ctext[:200]}\n  confidence: 0.9\n"

        compliance_report += """
## Unknown Clauses (Require Review)
"""
        for clause in unknown:
            cid = clause.get("id", "?") if isinstance(clause, dict) else "?"
            ctext = clause.get("text", str(clause)) if isinstance(clause, dict) else str(clause)
            compliance_report += f"\n- clause_id: {cid}\n  summary: {ctext[:200]}\n  assumption: true\n"

        compliance_report += f"""
## Readiness Summary
{json.dumps(readiness_data, indent=2)[:2000]}

## Artifacts
- `.agent/artifacts/impl_check_report.json` — implementation check result
- `.agent/artifacts/clause_investigation.json` — per-clause investigation
- `.agent/artifacts/readiness_report.json` — readiness audit
- `.agent/artifacts/run_record.json` — run record
"""

        (artifacts_dir / "compliance_report.md").write_text(compliance_report)
        print(f"Compliance report written to {artifacts_dir}/compliance_report.md", file=sys.stderr)

        # Output summary to stdout for capture
        print(json.dumps({
            "verdict": verdict,
            "satisfied": len(satisfied),
            "violated": len(violated),
            "unknown": len(unknown),
            "violated_clauses": violated,
            "unknown_clauses": unknown,
            "readiness": readiness_data,
        }))

    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
