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
  version: "1.1.0"
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

**Step classification:**

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| `register_repo` + `graph_build` | deterministic | Yes | `graph_index` (server-side) |
| `run_implementation_check` | deterministic (MCP-backed) | Yes | `impl_check_report.json` |
| Clause investigation | llm-reasoning | Yes | `clause_investigation.json` |
| `run_readiness_audit` | deterministic (MCP-backed) | Yes | `readiness_report.json` |
| Report synthesis | final-synthesis (read-only) | — | `compliance_report.md` |

**MCP tool:** `run_implementation_check(spec="<design_doc_text_or_clause>")`

Steps:
1. Register repo: `register_repo(repo_id="llm-sca-tooling", path=".")`
2. Build index: `graph_build(repo="llm-sca-tooling")`
3. Call `run_implementation_check(spec="<full spec text>")`; save as `impl_check_report.json`
4. For violated/unknown clauses — **LLM reasoning contract:**
   ```yaml
   required_inputs: [impl_check_report.json]
   allowed_tools: [run_static_analysis, get_relevant_files, capture_trace]
   forbidden_actions: [write_files, run_tests, edit_source]
   evidence_requirements:
     - every clause finding must cite file:line from MCP tool responses
     - confidence score required per clause
   assumption_handling: separate confirmed from inferred; label inferences assumption: true
   failure_policy: {retries: 1, then: block}
   ```
5. Save clause findings as `clause_investigation.json`; finish with `run_readiness_audit`

> **Final synthesis boundary:** the compliance report MUST NOT add findings absent from
> `impl_check_report.json` or `clause_investigation.json`.

---

## Workflow: `bug-resolve`

Locate, explain, fix, and verify a reported bug.

**Step classification:**

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| `retrieve_memory` + `get_relevant_files` | deterministic (MCP-backed) | Yes | `bug_context.json` |
| `capture_trace` (if reproduction available) | deterministic | Yes | `trace_artifact` |
| Root-cause analysis | llm-reasoning | Yes | `bug_analysis.json` |
| Patch generation | llm-reasoning | Yes | patch (staged diff) |
| `classify_patch_risk` | deterministic (MCP-backed) | Yes — block if `vulnerable` | `patch_risk.json` |
| `make verify` | deterministic | Yes | exit code |

**MCP tool:** `run_issue_resolution(issue_text="<bug_report>", repos=[…])`

Steps:
1. Call `retrieve_memory` + `get_relevant_files` for context; save as `bug_context.json`
2. If reproduction available: call `capture_trace` for dynamic evidence
3. **LLM reasoning contract for root-cause analysis:**
   ```yaml
   required_inputs: [bug_context.json, trace_artifact (if exists)]
   allowed_tools: [get_relevant_files, run_static_analysis, capture_trace]
   forbidden_actions: [edit_files, run_tests_directly]
   evidence_requirements:
     - root cause must cite file:line and optionally trace span
     - assumptions must be labeled separately from confirmed findings
   failure_policy: {retries: 1, then: block}
   ```
4. Save root-cause analysis as `bug_analysis.json`
5. Generate patch; call `classify_patch_risk` — block if `vulnerable`
6. Run `make verify` to confirm fix

---

## Workflow: `patch-review`

Review a diff for correctness, safety, compatibility, and side effects.

**Step classification:**

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| `run_patch_review` | deterministic (MCP-backed) | Yes | `patch_review_report.json` |
| `classify_patch_risk` | deterministic (MCP-backed) | Yes — block if `vulnerable` | `patch_risk.json` |
| `run_static_analysis` | deterministic | Yes — block on high/critical | `static_analysis.json` |
| Review synthesis | final-synthesis (read-only) | — | `patch_verdict.md` |

**MCP tool:** `run_patch_review(diff="<unified_diff>")`

Steps:
1. Call `run_patch_review(diff="<diff>")` — spawns 4-axis parallel review when sampling is available; save as `patch_review_report.json`
2. Call `classify_patch_risk` — must return `safe` or `correct-but-overfit`; save as `patch_risk.json`
3. Call `run_static_analysis` — no new high/critical alerts

> **Final synthesis boundary:** `patch_verdict.md` must cite only findings from
> `patch_review_report.json`, `patch_risk.json`, and `static_analysis.json`.
> Separate confirmed issues from assumptions. Require evidence (file:line) for every finding.

---

## Workflow: `readiness-audit`

Decide whether the tool can safely run higher-autonomy workflows.

**MCP tool:** `run_readiness_audit(repo="<repo_id>")`

Steps:
1. Call `run_readiness_audit` — reads readiness, governance policy, manifest state; save as `readiness_report.json`
2. Report: stage, per-axis scores, blockers, next-stage upgrade path

**Failure policy:** any per-axis regression blocks the workflow.

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
- All intermediate artifacts written to `.agent/artifacts/` before final synthesis
- Final synthesis cites only artifacts from this run
- `make verify` exits 0
- No new secrets or SAST findings

## Notes

- If `get_relevant_files` returns empty: run `graph_build` first
- MCP Sampling required for parallel patch-review subagents; falls back to single-agent mode
- See `references/mcp-workflow.md` for full JSON-RPC frame examples
