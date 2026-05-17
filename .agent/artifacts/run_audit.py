#!/usr/bin/env python3
"""Run the implementation-check workflow via the llm-sca-tooling MCP server."""

import json
import subprocess
import sys
import time
from pathlib import Path

ARTIFACTS = Path(__file__).parent
REPO_PATH = "/home/grammy-jiang/projects/research-pipeline"
ARCH_DOC = Path(REPO_PATH) / "docs" / "architecture.md"


def send_recv(proc, msg: dict, timeout: int = 30) -> dict:
    """Send a JSON-RPC message and return the parsed response."""
    line = json.dumps(msg) + "\n"
    proc.stdin.write(line)
    proc.stdin.flush()
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp_line = proc.stdout.readline()
        if not resp_line:
            time.sleep(0.1)
            continue
        resp_line = resp_line.strip()
        if not resp_line:
            continue
        # Skip INFO/log lines that go to stderr but might bleed through
        if resp_line.startswith("{"):
            try:
                parsed = json.loads(resp_line)
                # Match by id if present
                if "id" in parsed and parsed.get("id") == msg.get("id"):
                    return parsed
                # notifications have no id; skip them
            except json.JSONDecodeError:
                pass
    raise TimeoutError(f"No response for id={msg.get('id')} within {timeout}s")


def poll_task(proc, task_id: str, poll_interval: int = 5, max_wait: int = 300) -> dict:
    """Poll task_status until completed, then return task_result."""
    start = time.time()
    msg_id = 100
    while time.time() - start < max_wait:
        resp = send_recv(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "task_status", "arguments": {"task_id": task_id}},
                "id": msg_id,
            },
            timeout=15,
        )
        msg_id += 1
        payload = json.loads(resp["result"]["content"][0]["text"])
        status = payload["task"]["status"]
        pct = payload["task"]["progress"].get("percent", 0)
        print(f"  task_status: {status} ({pct}%)", flush=True)
        if status == "completed":
            # Get result
            result_resp = send_recv(
                proc,
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "task_result",
                        "arguments": {"task_id": task_id},
                    },
                    "id": msg_id,
                },
                timeout=15,
            )
            return json.loads(result_resp["result"]["content"][0]["text"])
        elif status in ("failed", "error"):
            raise RuntimeError(f"Task failed: {payload}")
        time.sleep(poll_interval)
    raise TimeoutError(f"Task {task_id} did not complete within {max_wait}s")


def main():
    arch_spec = ARCH_DOC.read_text()
    print(f"Architecture spec: {len(arch_spec)} chars", flush=True)

    # Start MCP server
    proc = subprocess.Popen(
        ["uv", "run", "llm-sca-tooling", "mcp", "serve", "--transport", "stdio"],
        cwd="/home/grammy-jiang/Documents/evidence-sca",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    time.sleep(4)  # wait for startup

    msg_id = 1

    # Step 1: Initialize
    print("Step 1: Initialize", flush=True)
    resp = send_recv(
        proc,
        {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agent", "version": "1"},
            },
            "id": msg_id,
        },
    )
    print(f"  server: {resp['result']['serverInfo']}", flush=True)
    msg_id += 1

    # Send initialized notification
    proc.stdin.write(
        json.dumps(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        )
        + "\n"
    )
    proc.stdin.flush()
    time.sleep(0.5)

    # Step 2: Register repo
    print("Step 2: Register repo", flush=True)
    resp = send_recv(
        proc,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "register_repo", "arguments": {"repo_path": REPO_PATH}},
            "id": msg_id,
        },
    )
    payload = json.loads(resp["result"]["content"][0]["text"])
    repo_id = payload["repo"]["repo_id"]
    print(f"  repo_id: {repo_id}", flush=True)
    msg_id += 1

    # Step 3: Build graph
    print("Step 3: Build graph", flush=True)
    resp = send_recv(
        proc,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "graph_build", "arguments": {"repo_path": REPO_PATH}},
            "id": msg_id,
        },
        timeout=20,
    )
    task_payload = json.loads(resp["result"]["content"][0]["text"])
    task_id = task_payload["task"]["task_id"]
    print(f"  task_id: {task_id}", flush=True)
    msg_id += 1

    print("  Polling graph build...", flush=True)
    graph_result = poll_task(proc, task_id, poll_interval=8, max_wait=300)
    print(f"  graph result keys: {list(graph_result.keys())}", flush=True)

    # Step 5: Run implementation check
    print("Step 5: Run implementation check", flush=True)
    resp = send_recv(
        proc,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "run_implementation_check",
                "arguments": {"spec": arch_spec},
            },
            "id": msg_id,
        },
        timeout=120,
    )
    impl_check_raw = resp["result"]["content"][0]["text"]
    impl_check = json.loads(impl_check_raw)
    (ARTIFACTS / "impl_check_report.json").write_text(json.dumps(impl_check, indent=2))
    print(f"  Saved impl_check_report.json", flush=True)
    print(
        f"  verdict: {impl_check.get('overall_verdict', impl_check.get('verdict', 'N/A'))}",
        flush=True,
    )
    msg_id += 1

    # Step 6: Run readiness audit
    print("Step 6: Run readiness audit", flush=True)
    resp = send_recv(
        proc,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "run_readiness_audit",
                "arguments": {"repo": REPO_PATH},
            },
            "id": msg_id,
        },
        timeout=120,
    )
    readiness_raw = resp["result"]["content"][0]["text"]
    readiness = json.loads(readiness_raw)
    (ARTIFACTS / "readiness_report.json").write_text(json.dumps(readiness, indent=2))
    print(f"  Saved readiness_report.json", flush=True)
    msg_id += 1

    # Step 7: Investigate violated/unknown clauses
    print("Step 7: Investigate clauses", flush=True)
    violated = impl_check.get("violated_clauses", [])
    unknown = impl_check.get("unknown_clauses", [])
    clauses_to_investigate = violated + unknown
    print(f"  violated: {len(violated)}, unknown: {len(unknown)}", flush=True)

    clause_findings = []
    for clause in clauses_to_investigate[:10]:  # cap at 10 to avoid timeout
        clause_id = clause.get("clause_id", clause.get("id", "unknown"))
        clause_text = clause.get("text", clause.get("description", str(clause)))
        topic = clause.get("topic", clause_id)
        print(f"  Investigating: {clause_id}", flush=True)

        # get_relevant_files
        try:
            resp = send_recv(
                proc,
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "get_relevant_files",
                        "arguments": {"repo": REPO_PATH, "query": topic},
                    },
                    "id": msg_id,
                },
                timeout=30,
            )
            files_raw = resp["result"]["content"][0]["text"]
            files_result = json.loads(files_raw)
            msg_id += 1
        except Exception as e:
            files_result = {"error": str(e)}
            msg_id += 1

        # run_static_analysis
        try:
            resp = send_recv(
                proc,
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "run_static_analysis",
                        "arguments": {
                            "repo": REPO_PATH,
                            "predicate": clause_text[:500],
                        },
                    },
                    "id": msg_id,
                },
                timeout=30,
            )
            sa_raw = resp["result"]["content"][0]["text"]
            sa_result = json.loads(sa_raw)
            msg_id += 1
        except Exception as e:
            sa_result = {"error": str(e)}
            msg_id += 1

        clause_findings.append(
            {
                "clause_id": clause_id,
                "clause_text": clause_text[:300],
                "relevant_files": files_result,
                "static_analysis": sa_result,
            }
        )

    (ARTIFACTS / "clause_investigation.json").write_text(
        json.dumps(clause_findings, indent=2)
    )
    print(
        f"  Saved clause_investigation.json ({len(clause_findings)} clauses)",
        flush=True,
    )

    # Step 8: Verify run record
    print("Step 8: Verify run record", flush=True)
    try:
        resp = send_recv(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "resources/read",
                "params": {"uri": "code-intelligence://runs/latest"},
                "id": msg_id,
            },
            timeout=15,
        )
        run_record_raw = resp.get("result", {})
        (ARTIFACTS / "run_record.json").write_text(json.dumps(run_record_raw, indent=2))
        print(f"  Saved run_record.json", flush=True)
        msg_id += 1
    except Exception as e:
        print(f"  Warning: run record read failed: {e}", flush=True)
        run_record_raw = {"error": str(e)}
        msg_id += 1

    proc.stdin.close()
    proc.wait(timeout=5)
    print("MCP server shut down.", flush=True)

    return {
        "repo_id": repo_id,
        "impl_check": impl_check,
        "readiness": readiness,
        "clause_findings": clause_findings,
        "run_record": run_record_raw,
    }


if __name__ == "__main__":
    results = main()
    print("\n=== Summary ===")
    ic = results["impl_check"]
    print(f"overall_verdict: {ic.get('overall_verdict', ic.get('verdict', 'N/A'))}")
    print(f"satisfied_clauses: {len(ic.get('satisfied_clauses', []))}")
    print(f"violated_clauses: {len(ic.get('violated_clauses', []))}")
    print(f"unknown_clauses: {len(ic.get('unknown_clauses', []))}")
