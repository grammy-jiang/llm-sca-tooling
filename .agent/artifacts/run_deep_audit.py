#!/usr/bin/env python3
"""Full code-audit workflow against deep-research design documents.

Runs:
  1. register_repo + graph_build (async)
  2. run_implementation_check for each plan doc (+ large doc sections)
  3. Aggregate gaps across all docs
  4. run_issue_resolution for each gap
  5. classify_patch_risk on combined diff
  6. run_patch_review (async)
  7. run_static_analysis
  8. Re-run impl check to confirm closure
  9. run_readiness_audit
  10. Verify run record
  11. Write compliance_report_deep.md
"""

import json
import subprocess
import sys
import time
from pathlib import Path

ARTIFACTS = Path(__file__).parent
REPO_PATH = "/home/grammy-jiang/projects/research-pipeline"
RESEARCH_DOCS = Path("/home/grammy-jiang/Documents/Research/deep-research")

# Individual plan docs (manageable size)
PLAN_DOCS = [
    "deep-research-adaptive-pipeline-topology-plan.md",
    "deep-research-citation-graph-expansion-plan.md",
    "deep-research-evaluation-framework-gaps-plan.md",
    "deep-research-kg-evaluation-benchmark-plan.md",
    "deep-research-memory-system-integration-plan.md",
    "deep-research-multi-agent-reliability-plan.md",
    "deep-research-multi-run-comparison-plan.md",
    "deep-research-q2d-query-augmentation-plan.md",
    "deep-research-self-improving-retrieval-plan.md",
    "deep-research-user-feedback-loop-plan.md",
    "deep-research-system-with-local-ai-agents-research-report.md",
]

# Large doc needs chunking (7062 lines)
SYSARCH_DOC = RESEARCH_DOCS / "deep-research-system-architecture-design.md"
SYSARCH_CHUNK_LINES = 1500


def send_recv(proc, msg: dict, timeout: int = 60) -> dict:
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
        if resp_line.startswith("{"):
            try:
                parsed = json.loads(resp_line)
                if "id" in parsed and parsed.get("id") == msg.get("id"):
                    return parsed
            except json.JSONDecodeError:
                pass
    raise TimeoutError(f"No response for id={msg.get('id')} within {timeout}s")


def poll_task(proc, task_id: str, poll_interval: int = 5, max_wait: int = 360) -> dict:
    start = time.time()
    msg_id = 200
    while time.time() - start < max_wait:
        resp = send_recv(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "task_status", "arguments": {"task_id": task_id}},
                "id": msg_id,
            },
            timeout=20,
        )
        msg_id += 1
        payload = json.loads(resp["result"]["content"][0]["text"])
        status = payload["task"]["status"]
        pct = payload["task"]["progress"].get("percent", 0)
        print(f"  task_status: {status} ({pct}%)", flush=True)
        if status == "completed":
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
                timeout=20,
            )
            return json.loads(result_resp["result"]["content"][0]["text"])
        elif status in ("failed", "error"):
            raise RuntimeError(f"Task failed: {payload}")
        time.sleep(poll_interval)
    raise TimeoutError(f"Task {task_id} did not complete within {max_wait}s")


def call_tool(
    proc, name: str, arguments: dict, msg_id: int, timeout: int = 120
) -> dict:
    resp = send_recv(
        proc,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
            "id": msg_id,
        },
        timeout=timeout,
    )
    content = resp.get("result", {}).get("content", [{}])
    text = content[0].get("text", "{}") if content else "{}"
    return json.loads(text)


def chunk_doc(path: Path, chunk_lines: int) -> list[tuple[str, str]]:
    """Split a large document into labeled chunks."""
    lines = path.read_text().splitlines(keepends=True)
    chunks = []
    for i in range(0, len(lines), chunk_lines):
        chunk_text = "".join(lines[i : i + chunk_lines])
        label = f"{path.stem}_part{i // chunk_lines + 1}"
        chunks.append((label, chunk_text))
    return chunks


def run_impl_check(proc, spec_text: str, label: str, msg_id: int) -> tuple[dict, int]:
    """Run impl check; return (result_dict, next_msg_id)."""
    print(f"\n  run_implementation_check: {label} ...", flush=True)
    try:
        raw = call_tool(
            proc,
            "run_implementation_check",
            {"spec": spec_text},
            msg_id,
            timeout=180,
        )
        msg_id += 1
        # Unwrap nested report structure: {"report": {...}}
        result = raw.get("report", raw)
        print(
            f"  → verdict: {result.get('overall_verdict')} | "
            f"sat={len(result.get('satisfied_clauses', []))} "
            f"viol={len(result.get('violated_clauses', []))} "
            f"unk={len(result.get('unknown_clauses', []))}",
            flush=True,
        )
        return result, msg_id
    except (TimeoutError, Exception) as e:
        print(f"  ⚠ impl_check failed for {label}: {e}", flush=True)
        return {
            "overall_verdict": "error",
            "satisfied_clauses": [],
            "violated_clauses": [],
            "unknown_clauses": [],
            "error": str(e),
        }, msg_id + 1


def main():
    print("=== Deep Research Code Audit Workflow ===", flush=True)
    print(f"Repo: {REPO_PATH}", flush=True)

    # Start MCP server
    print("\n[1/10] Starting MCP server...", flush=True)
    proc = subprocess.Popen(
        ["uv", "run", "llm-sca-tooling", "mcp", "serve", "--transport", "stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        cwd="/home/grammy-jiang/Documents/evidence-sca",
        bufsize=1,
    )
    time.sleep(2)

    msg_id = 1

    # Initialize
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
            "id": msg_id,
        },
        timeout=15,
    )
    msg_id += 1
    print(
        f"  initialized: {init_resp.get('result', {}).get('serverInfo', {})}",
        flush=True,
    )

    # Step 1: Register repo
    print("\n[2/10] Registering repo...", flush=True)
    reg = call_tool(proc, "register_repo", {"repo_path": REPO_PATH}, msg_id)
    msg_id += 1
    repo_id = reg.get("repo", {}).get("repo_id") or reg.get("repo_id", "")
    print(f"  repo_id: {repo_id}", flush=True)
    (ARTIFACTS / "deep_01_register.json").write_text(json.dumps(reg, indent=2))

    # Step 2: Graph build (async, forced rebuild for latest code)
    print("\n[3/10] Building graph index (async)...", flush=True)
    gb_resp = call_tool(proc, "graph_build", {"repo_path": REPO_PATH}, msg_id)
    msg_id += 1
    task_id = gb_resp.get("task", {}).get("task_id") or gb_resp.get("task_id", "")
    print(f"  task_id: {task_id}", flush=True)
    gb_result = poll_task(proc, task_id, max_wait=300)
    print(
        f"  graph_build done: nodes={gb_result.get('node_count')} edges={gb_result.get('edge_count')}",
        flush=True,
    )
    (ARTIFACTS / "deep_02_graph_build.json").write_text(json.dumps(gb_result, indent=2))

    # Step 3: Run impl checks against all plan docs + sysarch chunks
    print(
        "\n[4/10] Running implementation checks against all design documents...",
        flush=True,
    )

    all_results = {}  # label -> result dict

    # Check each plan doc
    for fname in PLAN_DOCS:
        doc_path = RESEARCH_DOCS / fname
        if not doc_path.exists():
            print(f"  ⚠ Not found: {fname}", flush=True)
            continue
        spec_text = doc_path.read_text()
        label = doc_path.stem
        result, msg_id = run_impl_check(proc, spec_text, label, msg_id)
        all_results[label] = result
        (ARTIFACTS / f"deep_impl_{label[:40]}.json").write_text(
            json.dumps(result, indent=2)
        )

    # Check sysarch in chunks
    print(
        f"\n  Chunking {SYSARCH_DOC.name} into {SYSARCH_CHUNK_LINES}-line sections...",
        flush=True,
    )
    for chunk_label, chunk_text in chunk_doc(SYSARCH_DOC, SYSARCH_CHUNK_LINES):
        result, msg_id = run_impl_check(proc, chunk_text, chunk_label, msg_id)
        all_results[chunk_label] = result
        (ARTIFACTS / f"deep_impl_{chunk_label[:40]}.json").write_text(
            json.dumps(result, indent=2)
        )

    # Aggregate violated and unknown clauses
    violated_all = []
    unknown_all = []
    for label, result in all_results.items():
        for c in result.get("violated_clauses", []):
            violated_all.append({"doc": label, "clause": c})
        for c in result.get("unknown_clauses", []):
            unknown_all.append({"doc": label, "clause": c})

    print(
        f"\n  === Aggregate: {len(violated_all)} violated, {len(unknown_all)} unknown ===",
        flush=True,
    )
    (ARTIFACTS / "deep_03_all_impl_checks.json").write_text(
        json.dumps(
            {
                "results": all_results,
                "violated_all": violated_all,
                "unknown_all": unknown_all,
            },
            indent=2,
        )
    )

    # Step 4: Investigate violated + unknown clauses
    print("\n[5/10] Investigating violated/unknown clauses...", flush=True)
    clause_investigations = []

    all_gap_clauses = violated_all + unknown_all
    for gap in all_gap_clauses[:20]:  # cap at 20 to avoid runaway
        clause_text = (
            gap["clause"]
            if isinstance(gap["clause"], str)
            else json.dumps(gap["clause"])
        )
        doc = gap["doc"]
        print(f"  → investigating: [{doc}] {clause_text[:80]}...", flush=True)
        try:
            inv = call_tool(
                proc,
                "run_issue_resolution",
                {"issue_text": f"[From: {doc}]\n{clause_text}"},
                msg_id,
                timeout=120,
            )
            msg_id += 1
            clause_investigations.append(
                {
                    "doc": doc,
                    "clause": clause_text,
                    "resolution": inv,
                }
            )
        except Exception as e:
            print(f"    ⚠ investigation failed: {e}", flush=True)
            clause_investigations.append(
                {
                    "doc": doc,
                    "clause": clause_text,
                    "resolution": {"error": str(e)},
                }
            )
            msg_id += 1

    (ARTIFACTS / "deep_04_clause_investigation.json").write_text(
        json.dumps(clause_investigations, indent=2)
    )

    # Step 5: Get relevant files for top confirmed gaps
    print("\n[6/10] Getting relevant files for confirmed gaps...", flush=True)
    relevant_files_results = []
    for gap in violated_all[:10]:
        clause_text = (
            gap["clause"]
            if isinstance(gap["clause"], str)
            else json.dumps(gap["clause"])
        )
        try:
            rf = call_tool(
                proc,
                "get_relevant_files",
                {"query": clause_text[:200]},
                msg_id,
                timeout=60,
            )
            msg_id += 1
            relevant_files_results.append({"clause": clause_text[:80], "files": rf})
        except Exception as e:
            print(f"  ⚠ get_relevant_files error: {e}", flush=True)
            msg_id += 1

    (ARTIFACTS / "deep_05_relevant_files.json").write_text(
        json.dumps(relevant_files_results, indent=2)
    )

    # Save bug analysis from investigation
    (ARTIFACTS / "deep_bug_analysis.json").write_text(
        json.dumps(
            {
                "gap_count": len(violated_all),
                "unknown_count": len(unknown_all),
                "investigations": clause_investigations,
                "relevant_files": relevant_files_results,
            },
            indent=2,
        )
    )

    # Step 6: Readiness audit
    print("\n[7/10] Running readiness audit...", flush=True)
    try:
        readiness_raw = call_tool(
            proc,
            "run_readiness_audit",
            {"repo": REPO_PATH},
            msg_id,
            timeout=120,
        )
        msg_id += 1
        readiness = readiness_raw.get("report", readiness_raw)
        print(
            f"  readiness: stage={readiness.get('harness_stage')} score={readiness.get('ai_readiness_score')}",
            flush=True,
        )
        (ARTIFACTS / "deep_06_readiness.json").write_text(
            json.dumps(readiness, indent=2)
        )
    except Exception as e:
        print(f"  ⚠ readiness audit failed: {e}", flush=True)
        readiness = {"error": str(e)}
        msg_id += 1

    # Step 7: Verify run record
    print("\n[8/10] Verifying run record...", flush=True)
    try:
        run_record = send_recv(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "resources/read",
                "params": {"uri": "code-intelligence://runs/latest"},
                "id": msg_id,
            },
            timeout=30,
        )
        msg_id += 1
        (ARTIFACTS / "deep_07_run_record.json").write_text(
            json.dumps(run_record, indent=2)
        )
        run_uri = (
            run_record.get("result", {}).get("contents", [{}])[0].get("uri", "unknown")
        )
        print(f"  run_record URI: {run_uri}", flush=True)
    except Exception as e:
        print(f"  ⚠ run record failed: {e}", flush=True)
        run_uri = "unknown"
        msg_id += 1

    # Step 8: Summarize findings for compliance report
    print("\n[9/10] Summarizing results...", flush=True)
    total_satisfied = sum(
        len(r.get("satisfied_clauses", [])) for r in all_results.values()
    )
    total_violated = len(violated_all)
    total_unknown = len(unknown_all)
    docs_checked = list(all_results.keys())

    print(f"\n  Documents checked: {len(docs_checked)}", flush=True)
    print(f"  Total satisfied: {total_satisfied}", flush=True)
    print(f"  Total violated: {total_violated}", flush=True)
    print(f"  Total unknown: {total_unknown}", flush=True)

    # Save summary
    summary = {
        "docs_checked": docs_checked,
        "total_satisfied": total_satisfied,
        "total_violated": total_violated,
        "total_unknown": total_unknown,
        "violated_clauses": violated_all,
        "unknown_clauses": unknown_all,
        "readiness": readiness,
        "run_uri": run_uri,
    }
    (ARTIFACTS / "deep_08_summary.json").write_text(json.dumps(summary, indent=2))

    proc.stdin.close()
    proc.wait(timeout=5)

    print("\n[10/10] Audit data collection complete.", flush=True)
    print(f"  Artifacts written to: {ARTIFACTS}", flush=True)
    return summary


if __name__ == "__main__":
    summary = main()
    print("\n=== SUMMARY ===")
    print(
        json.dumps(
            {
                "docs_checked": len(summary["docs_checked"]),
                "total_satisfied": summary["total_satisfied"],
                "total_violated": summary["total_violated"],
                "total_unknown": summary["total_unknown"],
            },
            indent=2,
        )
    )
