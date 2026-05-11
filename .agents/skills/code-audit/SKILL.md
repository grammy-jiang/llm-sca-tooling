---
name: code-audit
description: >
  Orchestrate design/spec compliance checks, bug resolution, patch review, and
  readiness audits using the llm-sca-tooling MCP server. Use when asked to audit
  implementation completeness against a design doc, review a patch or unified diff,
  resolve or investigate a bug report, run an operational review, or check readiness.
  Also use when the user says "check features", "audit implementation", "review this
  diff", "fix this bug", or "is the architecture satisfied". ALWAYS invoke the
  llm-sca-tooling MCP server — never substitute Python imports or external tools.
compatibility: >
  Requires Python 3.12+, uv, and the llm-sca-tooling package installed in the
  current repository. Start the MCP server before calling any tools:
  `uv run llm-sca-tooling mcp serve --transport stdio`
license: MIT
metadata:
  mcp-server: llm-sca-tooling
  mcp-transport: stdio
  version: "1.0.0"
---

# code-audit

> **MANDATORY — DO NOT SKIP:**
> All workflows in this skill MUST be executed via the `llm-sca-tooling` MCP
> server tools. You MUST NOT substitute Python imports, direct shell scripts, or
> any external tool (e.g., `local-agent-harness`) for MCP tool calls.
> Skipping this requirement defeats the purpose of this repository.

## Start the MCP server (required first step)

```bash
uv run llm-sca-tooling mcp serve --transport stdio
```

Initialize the session (send on stdin):

```json
{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"agent","version":"1"}},"id":1}
```

See `references/mcp-workflow.md` for full JSON-RPC examples.

---

## Workflow: `implementation-check`

Determine whether the current implementation satisfies a design/spec.

**MCP tool:** `run_implementation_check(spec="<design_doc_text_or_clause>")`

Steps:
1. Register repo: `register_repo(repo_id="llm-sca-tooling", path=".")`
2. Build index: `graph_build(repo="llm-sca-tooling")`
3. Call `run_implementation_check(spec="<full spec text>")`
4. For violated/unknown clauses: call `run_static_analysis` + `get_relevant_files`
5. Finish with `run_readiness_audit`

---

## Workflow: `bug-resolve`

Locate, explain, fix, and verify a reported bug.

**MCP tool:** `run_issue_resolution(issue_text="<bug_report>", repos=[…])`

Steps:
1. Call `retrieve_memory` + `get_relevant_files` for context
2. If reproduction available: call `capture_trace` for dynamic evidence
3. Generate patch; call `classify_patch_risk` — block if `vulnerable`
4. Run `make verify` to confirm fix

---

## Workflow: `patch-review`

Review a diff for correctness, safety, compatibility, and side effects.

**MCP tool:** `run_patch_review(diff="<unified_diff>")`

Steps:
1. Call `run_patch_review(diff="<diff>")` — spawns 4-axis parallel review when sampling is available
2. Call `classify_patch_risk` — must return `safe` or `correct-but-overfit`
3. Call `run_static_analysis` — no new high/critical alerts

---

## Workflow: `readiness-audit`

Decide whether the tool can safely run higher-autonomy workflows.

**MCP tool:** `run_readiness_audit(repo="<repo_id>")`

Steps:
1. Call `run_readiness_audit` — reads readiness, governance policy, manifest state
2. Report: stage, per-axis scores, blockers, next-stage upgrade path

---

## Verify Gate (all workflows)

```
make verify                  # full gate — exits 0
run_static_analysis          # no new high/critical findings
run_readiness_audit          # no per-axis regression
```

> Do NOT run `local-agent-harness check` as a substitute for `run_readiness_audit`.

## Completion Criteria

- Workflow invoked via MCP JSON-RPC (not Python import)
- Run record `code-intelligence://runs/{run_id}` exists
- `make verify` exits 0
- No new secrets or SAST findings

## Notes

- If `get_relevant_files` returns empty: run `graph_build` first
- MCP Sampling required for parallel patch-review subagents; falls back to single-agent mode
- See `references/mcp-workflow.md` for full JSON-RPC frame examples
