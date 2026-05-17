---
name: audit
description: >
  Audit code against designs, specs, or bug reports; review patches; check
  readiness. Use when asked to: check if features or functions are fully
  implemented, audit against a design or architecture doc, review a patch or
  unified diff, resolve or investigate a bug report, run an operational review,
  or assess AI-readiness. Also use when the user says "check features", "audit
  implementation", "review this diff", "fix this bug", "investigate", or "is
  the architecture satisfied". ALWAYS invoke the llm-sca-tooling MCP server —
  never read docs and write checks manually, never substitute Python imports or
  external tools.
compatibility: >
  Requires Python 3.12+, uv, and the llm-sca-tooling package installed in the
  current repository. MCP server must be running before any tool calls:
  `uv run llm-sca-tooling mcp serve --transport stdio`
license: MIT
metadata:
  mcp-server: llm-sca-tooling
  mcp-transport: stdio
  version: "2.0.0"
---

# audit

> **MANDATORY — DO NOT SKIP:**
> All workflows MUST be executed via the `llm-sca-tooling` MCP server tools.
> You MUST NOT read docs and write checks manually, import Python modules
> directly, or use `local-agent-harness` as a substitute for MCP tool calls.

## Workflow routing

| User request | Workflow |
|---|---|
| "check features", "audit implementation", "is the architecture satisfied" | `implementation-check` |
| "fix this bug", "investigate", "resolve issue" | `bug-resolve` |
| "review this diff", "review this patch" | `patch-review` |
| "check readiness", "operational review" | `readiness-audit` |

## Start the MCP server (required first step)

```bash
uv run llm-sca-tooling mcp serve --transport stdio
```

Initialize the session:

```json
{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"agent","version":"1"}},"id":1}
```

See `references/mcp-workflow.md` for full JSON-RPC examples and async polling.

---

## Workflow: `implementation-check`

Determine whether the current implementation satisfies a design/spec.

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| `register_repo` | deterministic | Yes | `repo_id` (server-side) |
| `graph_build` | deterministic (async) | Yes | graph index (server-side) |
| `run_implementation_check` | deterministic (MCP-backed) | Yes | `impl_check_report.json` |
| Clause investigation | llm-reasoning | Yes | `clause_investigation.json` |
| `run_readiness_audit` | deterministic (MCP-backed) | Yes | `readiness_report.json` |
| Report synthesis | final-synthesis (read-only) | — | `compliance_report.md` |

**1. Register repo:**
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"register_repo","arguments":{"repo_path":"/absolute/path/to/repo"}},"id":2}
```
Note `payload.repo.repo_id` for subsequent calls.

**2. Build graph index (async):**
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"graph_build","arguments":{"repo_path":"/absolute/path/to/repo"}},"id":3}
```
Poll `task_status` → `task_result` until `"completed"` before proceeding.

**3. Run implementation check:**
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_implementation_check","arguments":{"spec":"<full spec text>"}},"id":4}
```
Save as `impl_check_report.json`. Key fields: `satisfied_clauses`, `violated_clauses`, `unknown_clauses`, `overall_verdict`.

**4. Investigate violated/unknown clauses** — LLM reasoning:
```yaml
required_inputs: [impl_check_report.json]
allowed_tools: [run_static_analysis, get_relevant_files, capture_trace]
forbidden_actions: [write_files, run_tests, edit_source, direct_file_reads, bash_grep]
evidence_requirements:
  - every clause finding must cite file:line from MCP tool responses
  - confidence score (0.0–1.0) required per clause
  - ALL file lookups MUST use get_relevant_files MCP tool (not grep/bash/view)
```
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_relevant_files","arguments":{"query":"<clause text>"}},"id":5}
```
Save findings as `clause_investigation.json`.

**5. Run readiness audit:**
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"<repo_path_or_id>"}},"id":6}
```
Save as `readiness_report.json`.

**6. Produce `compliance_report.md`** (read-only — cite only artifacts from this run):

```markdown
## Compliance Summary
- overall_verdict: <from impl_check_report.json>
- satisfied_clauses: <count>
- violated_clauses: <count>
- unknown_clauses: <count>

## Confirmed Gaps
- clause_id: <id>
  summary: <description>
  evidence: <file:line from clause_investigation.json>
  confidence: <0.0–1.0>

## Readiness Blockers
- <from readiness_report.json per-axis scores>

## Next Steps
- compliant → no action required
- partially_compliant → transition to bug-resolve for each confirmed gap
- non_compliant → block; escalate to human review
```

**Transition to `bug-resolve`:** when `violated_clauses` exist, run one `bug-resolve` cycle per gap using `impl_check_report.json` + `clause_investigation.json` as starting context.

---

## Workflow: `bug-resolve`

Locate, explain, fix, and verify a reported bug or implementation gap.

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Context collection | deterministic (MCP-backed) | Yes | `bug_context.json` |
| `capture_trace` (if repro available) | deterministic | Yes | `trace_artifact` |
| Root-cause analysis | llm-reasoning | Yes | `bug_analysis.json` |
| Patch generation | llm-reasoning | Yes | patch diff |
| `classify_patch_risk` | deterministic (MCP-backed) | Yes | `patch_risk.json` |
| `make verify` | deterministic | Yes | exit code |
| `patch-review` | deterministic (MCP-backed) | Yes | `patch_review_report.json` |

**1. Collect context:**
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_issue_resolution","arguments":{"issue_text":"<bug description>"}},"id":7}
```

**2. Capture trace** (if reproduction script available):
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"capture_trace","arguments":{"script":"<reproduction script>"}},"id":8}
```

**3. Root-cause analysis** — LLM reasoning:
```yaml
required_inputs: [bug_context.json, trace_artifact (if exists)]
allowed_tools: [get_relevant_files, run_static_analysis, capture_trace]
forbidden_actions: [edit_files, run_tests_directly]
evidence_requirements:
  - root cause must cite file:line and optionally trace span
```
Save as `bug_analysis.json`.

**4. Generate and stage patch.** Do not commit yet.

**5. Classify patch risk:**
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"classify_patch_risk","arguments":{"diff":"<unified diff>"}},"id":9}
```
- `safe` or `correct-but-overfit` → proceed.
- `unknown` or `review-required` → STOP; escalate to human.
- `vulnerable` or `vulnerability-introducing` → STOP immediately; do not commit.

**6. Run `make verify`** — must exit 0.

**7. Run `patch-review`** (see below) — mandatory before committing.

---

## Workflow: `patch-review`

Review a diff for correctness, safety, compatibility, and side effects.
Run after every `bug-resolve` fix before committing.

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| `run_patch_review` | deterministic (MCP-backed) | Yes | `patch_review_report.json` |
| `classify_patch_risk` | deterministic (MCP-backed) | Yes | `patch_risk.json` |
| `run_static_analysis` (MCP) | deterministic (MCP-backed) | Yes | `static_analysis.json` |
| Review synthesis | final-synthesis (read-only) | — | `patch_verdict.md` |

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_patch_review","arguments":{"diff":"<unified_diff>"}},"id":10}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"classify_patch_risk","arguments":{"diff":"<unified diff>"}},"id":11}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_static_analysis","arguments":{"repo_path":"<absolute/path>"}},"id":12}
```

Produce `patch_verdict.md` citing only findings from the three artifacts above.

---

## Workflow: `readiness-audit`

Decide whether the codebase is ready for higher-autonomy workflows.

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"<repo_path_or_id>"}},"id":13}
```
Save as `readiness_report.json`. Report: stage, per-axis scores, blockers, next-stage path. Any per-axis regression blocks the workflow.

---

## Verify Gate (all workflows)

```bash
make verify              # full gate — must exit 0
```
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_static_analysis","arguments":{"repo_path":"<path>"}},"id":99}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"<path>"}},"id":100}
```

## Completion Criteria

- All MCP tool calls executed via JSON-RPC (not Python import, not bash script)
- File investigations used `get_relevant_files` MCP tool (not grep/bash/view)
- Run record `code-intelligence://runs/{run_id}` confirmed via `resources/read`
- Intermediate artifacts written to `.agent/artifacts/` before final synthesis
- Final synthesis cites only artifacts from this run
- `make verify` exits 0; no new secrets or SAST findings
- If gaps fixed: re-run `run_implementation_check` to confirm closure
- For commit/tag/publish: invoke the `ship` skill after all gates pass

## Notes

- `register_repo` requires `repo_path` (absolute path). Not `path`. Not `repo_id`.
- `graph_build` is async — poll `task_status` → `task_result` before proceeding.
- `run_patch_review` with `"task":true` is also async — same poll pattern.
- If `get_relevant_files` returns empty: run `graph_build` first.
- See `references/mcp-workflow.md` for full JSON-RPC frame examples.
