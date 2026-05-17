#!/usr/bin/env python3
"""Investigate unknown clauses via MCP server get_relevant_files + run_static_analysis."""

import json
import subprocess
import sys
import time
from pathlib import Path

ARTIFACTS = Path(__file__).parent
REPO_PATH = "/home/grammy-jiang/projects/research-pipeline"

# Unknown clause topics derived from architecture.md — mapping clause IDs to topics
# We'll use the architecture's known topics to investigate each unknown clause
ARCH_TOPICS = [
    "plan stage QueryPlan cmd_plan.py",
    "search stage candidates.jsonl cmd_search.py sources",
    "screen stage BM25 heuristic scoring cheap_scores.jsonl shortlist.json",
    "screen SPECTER2 semantic re-ranking embeddings",
    "download stage PDF downloader rate limiting retry",
    "convert stage PDF to Markdown backends registry",
    "convert docling backend",
    "convert marker backend",
    "convert pymupdf4llm backend",
    "convert mathpix backend",
    "convert datalab backend",
    "convert llamaparse backend",
    "convert mistral_ocr backend",
    "convert openai_vision backend",
    "FallbackConverter fallback_backends multi-account rotation",
    "extract stage Markdown chunking BM25 index extraction",
    "summarize stage per-paper cross-paper synthesis",
    "expand citation graph Semantic Scholar CitationGraphClient",
    "quality evaluation composite score citation_metrics venue_scoring author_metrics",
    "convert_rough Tier 2 fast pymupdf4llm bulk conversion",
    "convert_fine Tier 3 high-quality selected papers",
    "index SQLite global paper index incremental dedup GlobalPaperIndex",
    "retry decorator exponential backoff infra/retry.py",
    "RateLimiter ArxivRateLimiter thread-safe rate limiting",
    "configuration TOML environment variables defaults",
    "run_manifest.json artifact hashing stage records",
    "cache HTTP responses TTL infra/cache.py",
    "logging JSONL structured logging infra/logging.py",
    "SearchSource protocol ArxivSource ScholarlySource SemanticScholarSource OpenAlexSource DBLPSource",
    "CandidateRecord model multi-source metadata doi semantic_scholar_id",
    "MCP server FastMCP tools stdio transport",
    "mcp_server tools plan_topic search screen_candidates download_pdfs convert_pdfs",
    "mcp_server extract_content summarize_papers run_pipeline get_run_manifest",
    "mcp_server convert_file list_backends",
    "pipeline orchestrator stage sequencing",
    "storage workspace management manifests artifacts",
    "models Pydantic v2 domain models",
    "config models per-backend Account Config",
    "deduplication arXiv ID DOI normalized title",
    "enrichment fill missing abstracts Semantic Scholar DOI lookup",
    "LLM judge final pass screening",
    "arXiv API Atom XML parser",
    "openai provider llm interface experimental",
    "conversion manifest ConvertManifestEntry retry_count last_error",
    "screening heuristic.py embedding.py RelevanceDecision CheapScoreBreakdown",
    "quality data core_rankings.json CORE rankings 120 venues",
    "summarization PaperSummary SynthesisReport synthesis.md",
    "run_manifest run_id timestamps configuration stage_records artifact_records SHA-256",
    "infra hashing clock HTTP",
    "models DownloadManifestEntry download manifest",
    "models ChunkMetadata MarkdownExtraction extraction",
    "models QualityScore quality",
    "models ConvertManifestEntry conversion manifest",
    "models screening CheapScoreBreakdown RelevanceDecision",
    "models candidate CandidateRecord",
    "models query_plan QueryPlan",
    "models summary PaperSummary SynthesisReport",
]


def send_recv(proc, msg: dict, timeout: int = 30) -> dict:
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


def poll_task(proc, task_id: str, poll_interval: int = 8, max_wait: int = 300) -> dict:
    msg_id = 200
    start = time.time()
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
                timeout=15,
            )
            return json.loads(result_resp["result"]["content"][0]["text"])
        elif status in ("failed", "error"):
            raise RuntimeError(f"Task failed: {payload}")
        time.sleep(poll_interval)
    raise TimeoutError(f"Task did not complete within {max_wait}s")


def main():
    impl_check = json.loads((ARTIFACTS / "impl_check_report.json").read_text())[
        "report"
    ]
    unknown_clause_ids = impl_check.get("unknown_clauses", [])
    print(f"Unknown clauses to investigate: {len(unknown_clause_ids)}", flush=True)

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
    time.sleep(4)

    msg_id = 1

    # Initialize
    send_recv(
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
    msg_id += 1
    proc.stdin.write(
        json.dumps(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        )
        + "\n"
    )
    proc.stdin.flush()
    time.sleep(0.5)

    # Register repo
    resp = send_recv(
        proc,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "register_repo", "arguments": {"repo_path": REPO_PATH}},
            "id": msg_id,
        },
    )
    msg_id += 1

    # Build graph
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
    task_id = json.loads(resp["result"]["content"][0]["text"])["task"]["task_id"]
    msg_id += 1
    poll_task(proc, task_id)

    clause_findings = []

    # Investigate each architecture topic
    for i, topic in enumerate(ARCH_TOPICS):
        clause_id = (
            unknown_clause_ids[i] if i < len(unknown_clause_ids) else f"topic:{i}"
        )
        print(
            f"  [{i + 1}/{len(ARCH_TOPICS)}] Investigating: {clause_id} — {topic[:50]}",
            flush=True,
        )

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
            files_result = json.loads(resp["result"]["content"][0]["text"])
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
                        "arguments": {"repo": REPO_PATH, "predicate": topic},
                    },
                    "id": msg_id,
                },
                timeout=30,
            )
            sa_result = json.loads(resp["result"]["content"][0]["text"])
            msg_id += 1
        except Exception as e:
            sa_result = {"error": str(e)}
            msg_id += 1

        clause_findings.append(
            {
                "clause_id": clause_id,
                "topic": topic,
                "relevant_files": files_result,
                "static_analysis": sa_result,
            }
        )

    (ARTIFACTS / "clause_investigation.json").write_text(
        json.dumps(clause_findings, indent=2)
    )
    print(
        f"Saved clause_investigation.json ({len(clause_findings)} entries)", flush=True
    )

    proc.stdin.close()
    proc.wait(timeout=5)


if __name__ == "__main__":
    main()
    print("Done.", flush=True)
