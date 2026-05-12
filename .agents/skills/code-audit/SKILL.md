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
  version: "1.2.0"
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

See `references/mcp-workflow.md` for full JSON-RPC examples including async polling.

---

## Workflow: `implementation-check`

Determine whether the current implementation satisfies a design/spec.

**Step classification:**

| Step | ID | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|---|
| `register_repo` | `register-repo` | deterministic | Yes | `repo_id` (server-side) |
| `graph_build` | `graph-build` | deterministic (async) | Yes | `graph_index` (server-side) |
| `run_implementation_check` | `impl-check` | deterministic (MCP-backed) | Yes | `impl_check_report.json` |
| Clause investigation | `clause-investigation` | llm-reasoning | Yes | `clause_investigation.json` |
| `run_readiness_audit` | `readiness-audit` | deterministic (MCP-backed) | Yes | `readiness_report.json` |
| Verify run record | `run-record` | deterministic | Yes | confirmed run URI |
| Report synthesis | `final-report` | final-synthesis (read-only) | — | `compliance_report.md` |

**Artifact handoff:**
```
register_repo → repo_id
  → graph_build (async: poll task_status → task_result)
    → run_implementation_check → impl_check_report.json
      → clause_investigation.json
        → readiness_report.json
          → compliance_report.md
```

**Steps:**

**1. Register repo** — `repo_path` is required (not `path`); provide the absolute filesystem path:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"register_repo","arguments":{"repo_path":"/absolute/path/to/repo"}},"id":2}
```

Note the `repo_id` from the response (`payload.repo.repo_id`) for subsequent calls.

**2. Build graph index (async)** — use `repo_path` (absolute) or `repo_id` from step 1:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"graph_build","arguments":{"repo_path":"/absolute/path/to/repo"}},"id":3}
```

`graph_build` returns `"status":"accepted"` with a `task_id`. Poll until complete:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"task_status","arguments":{"task_id":"<task_id>"}},"id":4}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"task_result","arguments":{"task_id":"<task_id>"}},"id":5}
```

See `references/mcp-workflow.md` for the full polling loop. Do not proceed until `task_status` shows `"completed"`.

**3. Run implementation check** — pass the full spec text:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_implementation_check","arguments":{"spec":"<full spec text>"}},"id":6}
```

Save as `impl_check_report.json`. Response fields: `satisfied_clauses`, `violated_clauses`, `unknown_clauses`, `overall_verdict`.

**4. Investigate violated/unknown clauses** — **LLM reasoning contract:**

```yaml
required_inputs: [impl_check_report.json]
allowed_tools: [run_static_analysis, get_relevant_files, capture_trace]
forbidden_actions: [write_files, run_tests, edit_source]
evidence_requirements:
  - every clause finding must cite file:line from MCP tool responses
  - confidence score (0.0–1.0) required per clause
assumption_handling: separate confirmed from inferred; label inferences assumption: true
failure_policy: {retries: 1, then: block}
```

Save clause findings as `clause_investigation.json`.

**5. Run readiness audit:**

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"<repo_path_or_id>"}},"id":7}
```

Save as `readiness_report.json`.

**6. Verify run record:**

```json
{"jsonrpc":"2.0","method":"resources/read","params":{"uri":"code-intelligence://runs/latest"},"id":8}
```

Confirm run record URI (`code-intelligence://runs/{run_id}`) exists; record it in the session plan.

**7. Produce `compliance_report.md`** — **final-synthesis (read-only):**

> MUST NOT add findings absent from `impl_check_report.json` or `clause_investigation.json`.
> Every claim must cite the artifact and field it originates from.

Required structure:

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

## Assumptions and Uncertainties
- clause_id: <id>
  why_uncertain: <reason>
  assumption: true

## Readiness Blockers
- <from readiness_report.json per-axis scores>

## Next Steps
- compliant → no action required
- partially_compliant → transition to bug-resolve for each confirmed gap (see below)
- non_compliant → block; escalate to human review
```

---

## Workflow transition: `implementation-check` → `bug-resolve`

When `implementation-check` produces `violated_clauses` or confirmed-gap `unknown_clauses`,
transition to `bug-resolve` for each gap. Pass `impl_check_report.json` and
`clause_investigation.json` as the starting context — these replace the `bug_context.json`
collection step when the gap was discovered by `implementation-check`.

**Transition checklist:**
- [ ] `compliance_report.md` written (gate before any fixes)
- [ ] One `bug-resolve` cycle per confirmed gap (batch if gaps share root cause)
- [ ] After all fixes: run `patch-review` on the combined diff (see below)
- [ ] Re-run `run_implementation_check` to confirm gaps are closed
- [ ] After gaps closed: proceed to `release` skill for commit → tag → publish pipeline

---

## Workflow: `bug-resolve`

Locate, explain, fix, and verify a reported bug or implementation gap.

**Step classification:**

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Context collection | deterministic (MCP-backed) | Yes | `bug_context.json` |
| `capture_trace` (if reproduction available) | deterministic | Yes | `trace_artifact` |
| Root-cause analysis | llm-reasoning | Yes | `bug_analysis.json` |
| Patch generation | llm-reasoning | Yes | patch (staged diff) |
| `classify_patch_risk` | deterministic (MCP-backed) | Yes — block if `vulnerable` | `patch_risk.json` |
| `make verify` | deterministic | Yes | exit code |
| `patch-review` | deterministic (MCP-backed) | Yes — block if risk `vulnerable` | `patch_review_report.json` |

**MCP tool:** `run_issue_resolution(issue_text="<bug_report>")`

**Steps:**

**1. Collect context:**

- If transitioning from `implementation-check`: `bug_context.json` = `impl_check_report.json` + `clause_investigation.json` (already available — skip to step 3).
- If a standalone bug report: call `retrieve_memory` + `get_relevant_files` and save as `bug_context.json`.

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_issue_resolution","arguments":{"issue_text":"<bug description or clause text>"}},"id":10}
```

**2. Capture trace** (if reproduction script available):

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"capture_trace","arguments":{"script":"<reproduction script>"}},"id":11}
```

**3. Root-cause analysis** — **LLM reasoning contract:**

```yaml
required_inputs: [bug_context.json, trace_artifact (if exists)]
allowed_tools: [get_relevant_files, run_static_analysis, capture_trace]
forbidden_actions: [edit_files, run_tests_directly]
evidence_requirements:
  - root cause must cite file:line and optionally trace span
  - assumptions must be labeled separately from confirmed findings
failure_policy: {retries: 1, then: block}
```

Save as `bug_analysis.json`.

**4. Generate patch** and stage it (do not commit yet).

**5. Classify patch risk** — block if `vulnerable` or `vulnerability-introducing`:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"classify_patch_risk","arguments":{"diff":"<unified diff of patch>"}},"id":12}
```

Save as `patch_risk.json`. Allowed classes to proceed: `safe`, `correct-but-overfit`.

**6. Run `make verify`** — must exit 0 before advancing.

**7. Run `patch-review`** (mandatory after every fix — see workflow below).

---

## Workflow: `patch-review`

Review a diff for correctness, safety, compatibility, and side effects.
**Must be run after every `bug-resolve` fix before committing.**

**Step classification:**

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| `run_patch_review` | deterministic (MCP-backed) | Yes | `patch_review_report.json` |
| `classify_patch_risk` | deterministic (MCP-backed) | Yes — block if `vulnerable` | `patch_risk.json` |
| `run_static_analysis` | deterministic | Yes — block on high/critical | `static_analysis.json` |
| Review synthesis | final-synthesis (read-only) | — | `patch_verdict.md` |

**Steps:**

**1.** Call `run_patch_review`:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_patch_review","arguments":{"diff":"<unified_diff>"}},"id":13}
```

Spawns 4-axis parallel review when MCP Sampling is available; falls back to single-agent mode. Save as `patch_review_report.json`.

**2.** Call `classify_patch_risk` — must return `safe` or `correct-but-overfit`; save as `patch_risk.json`.

**3.** Call `run_static_analysis` — no new high/critical alerts; save as `static_analysis.json`.

**4. Produce `patch_verdict.md`** (final-synthesis, read-only):

> Must cite only findings from `patch_review_report.json`, `patch_risk.json`, and `static_analysis.json`.
> Separate confirmed issues from assumptions. Require evidence (file:line) for every finding.

---

## Workflow: `readiness-audit`

Decide whether the tool can safely run higher-autonomy workflows.

**MCP tool:** `run_readiness_audit(repo="<repo_path_or_registered_id>")`

**Steps:**

1. Call `run_readiness_audit`; save as `readiness_report.json`.
2. Report: stage, per-axis scores, blockers, next-stage upgrade path.

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
- Run record `code-intelligence://runs/{run_id}` confirmed via `resources/read`
- All intermediate artifacts written to `.agent/artifacts/` before final synthesis
- `compliance_report.md` written with required structure (every claim cites an artifact)
- For `bug-resolve`: `bug_analysis.json`, `patch_risk.json`, `patch_review_report.json` all exist
- Final synthesis cites only artifacts from this run
- `make verify` exits 0
- No new secrets or SAST findings
- If gaps were fixed: re-run `run_implementation_check` to confirm closure
- For commit/tag/publish: invoke the `release` skill after all gates pass

## Notes

- `register_repo` requires `repo_path` (absolute or relative filesystem path). **Not** `path`. **Not** `repo_id`.
- `graph_build` requires `repo_path` (absolute path) **or** `repo_id` (the ID returned by `register_repo`). **Not** `repo`.
- `graph_build` is async: it returns `"status":"accepted"` with a `task_id`. Always poll `task_status` → `task_result` before proceeding.
- `run_patch_review` with `"task":true` is also async — same poll pattern applies.
- If `get_relevant_files` returns empty: run `graph_build` first.
- MCP Sampling required for parallel patch-review subagents; falls back to single-agent mode.
- See `references/mcp-workflow.md` for full JSON-RPC frame examples including async polling.
