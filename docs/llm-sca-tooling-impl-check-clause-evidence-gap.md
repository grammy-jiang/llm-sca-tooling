# llm-sca-tooling — Implementation-Check Clause-Evidence Gap

> **Status**: open — blocks the `audit` skill's `implementation-check` workflow
> from satisfying its own evidence requirements when the `run_implementation_check`
> tool returns any `unknown_clauses`.
>
> **Affects phase(s)**: Phase 4 (MCP server core — resource handlers),
> Phase 14 (implementation-check workflow — clause-evidence tooling).
>
> **First observed**: 2026-05-13 audit run against `research-pipeline`.
> **Reproduced**: 2026-05-17 13:43, 2026-05-17 17:03 (three consecutive runs).
> **Server version under test**: `llm-sca-tooling 0.3.4`, MCP server v3.2.4
> (stdio transport).

---

## TL;DR

When `run_implementation_check` returns any clauses in `report.unknown_clauses`,
the `audit` skill (`/home/grammy-jiang/.claude/skills/audit/SKILL.md`) requires
the auditor to investigate each one with `file:line` evidence and a confidence
score per clause. The skill specifies `get_relevant_files` as the canonical
MCP tool for this lookup. That tool is **not exposed** by the current MCP
server, and **four supporting resource URI schemes** referenced by the
implementation-check report itself also have no handlers.

The net effect: `partially_compliant` (the verdict produced when unknowns
exist) becomes an unresolvable terminal state for any consumer that follows
the skill strictly. The codebase under audit was correct in all three runs
— the verdict could not be improved by code changes, only by tooling fixes.

## Symptoms — exact MCP transcripts

All evidence below was captured against `research-pipeline` at git SHA
`242f13421a8d7aa3324255b297487a157f7df03a` (HEAD on `master`,
`chore: bump version to 0.17.35`). Raw artifacts live under
`/home/grammy-jiang/projects/research-pipeline/.agent/artifacts/iterative-2/`
and `.../iterative/`.

### 1. `get_relevant_files` is absent from `tools/list`

```jsonc
// Request
{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}

// Response (excerpted from iterative-2/00_tools_list.json)
// 17 tools advertised — none named "get_relevant_files":
//   register_repo, graph_build, graph_update, plugin_reload,
//   run_static_analysis, run_eval_suite, run_operational_review,
//   run_readiness_audit, run_patch_review, run_sast_repair,
//   run_issue_resolution, run_implementation_check, memory_compact,
//   task_status, task_result, task_cancel, task_list
```

The skill assumes this tool exists:

> The skill specifies `get_relevant_files` as the canonical MCP tool for
> clause-level evidence lookup.
> — `/home/grammy-jiang/.claude/skills/audit/SKILL.md` (forbidden_actions
> explicitly blocks `direct_file_reads, bash_grep` as substitutes).

There is no fallback path in the skill when this tool is missing. The
strict workflow halts.

### 2. Resource URIs returned by `run_implementation_check` have no handlers

`run_implementation_check` returns a report containing four URI references
that look like they should be `resources/read`-able (`04_impl_check_report.json`):

```json
{
  "report_id": "impl-check:impl-check:4f7337b4",
  "run_id": "impl-check:4f7337b4",
  "doc_id": "spec:2ca0065c",
  "spec_document_ref":          "spec://spec:2ca0065c",
  "intent_graph_ref":           "intent-graph://intent:spec:2ca0065c:4b01b0d0",
  "clause_verdict_matrix_ref":  "matrix://impl-check:4f7337b4",
  "session_trace_manifest_ref": "trace://impl-check:4f7337b4"
}
```

All four schemes return the same `Internal error` from `resources/read`:

```jsonc
// Request
{"jsonrpc":"2.0","id":N,"method":"resources/read",
 "params":{"uri":"matrix://impl-check:4f7337b4"}}

// Response (from iterative-2/11_matrix_impl-check.json)
{"jsonrpc":"2.0","id":N,
 "error":{"code":-32603,"message":"Internal error",
          "data":"No resource handler for 'matrix://impl-check:4f7337b4'"}}
```

Identical responses (with different URIs) are saved as:

| URI attempted | Artifact |
|---|---|
| `matrix://impl-check:4f7337b4` | `iterative-2/11_matrix_impl-check.json` |
| `spec://spec:2ca0065c` | `iterative-2/11_spec_doc.json` |
| `intent-graph://intent:spec:2ca0065c:4b01b0d0` | `iterative-2/11_intent_graph.json` |
| `trace://impl-check:4f7337b4` | `iterative-2/11_trace.json` |

### 3. The `code-intelligence://runs/{run_id}` resource also fails for impl-check run ids

The `resources/list` enumeration (`iterative-2/10_resources_list.json`) does
advertise this template:

```
code-intelligence://runs/{run_id}: run-record
code-intelligence://runs/{run_id}/harness-condition: run-harness-condition
```

…but calling it with the run id returned by `run_implementation_check`
fails:

```jsonc
// Request
{"jsonrpc":"2.0","id":N,"method":"resources/read",
 "params":{"uri":"code-intelligence://runs/impl-check:4f7337b4"}}

// Response (from iterative-2/11_run_record.json — error)
{"jsonrpc":"2.0","id":N,
 "error":{"code":-32603,"message":"Internal error",
          "data":"... (run not found / handler error)"}}
```

The handler accepts the URI template but does not resolve `impl-check:*`
run ids. (Possibly tied to a missing run-record write in the
implementation-check pipeline, or to a missing alias from `impl-check:*`
ids into the unified `run:*` namespace.)

### 4. `resources/templates/list` is not implemented

```jsonc
// Request
{"jsonrpc":"2.0","id":N,"method":"resources/templates/list","params":{}}

// Response (from iterative-2/10_resources_templates_list.json)
{"jsonrpc":"2.0","id":N,
 "error":{"code":-32601,"message":"Method not found: resources/templates/list"}}
```

This is a smaller issue — `resources/list` already returns the templates
inline — but downstream MCP clients that follow the standard
`templates/list` route get a hard `-32601`.

### 5. Manifest-state scanner false-negative (lower priority, recurring)

```jsonc
// Request
{"jsonrpc":"2.0","id":N,"method":"resources/read",
 "params":{"uri":"code-intelligence://governance/repo:8ff002e647ce33968a571786/manifest-state"}}

// Response (from iterative-2/11_manifest_state.json)
{
  "repo_id": "repo:8ff002e647ce33968a571786",
  "agents_md_present": false,
  "claude_md_present": false,
  "copilot_instructions_present": false,
  "codex_instructions_present": false,
  "drift_findings": [{"artefact": "AGENTS.md", "state": "missing"}, ...]
}
```

…but on disk:

```
/home/grammy-jiang/projects/research-pipeline/AGENTS.md         # present (385 lines)
/home/grammy-jiang/projects/research-pipeline/CLAUDE.md         # present (imports AGENTS.md)
/home/grammy-jiang/projects/research-pipeline/.github/copilot-instructions.md  # present
```

Confirmed via `test -f` in all three audit runs. The `run_readiness_audit`
tool, which uses a different scanner, correctly reports
`drift_findings: []` for the same repo (`iterative-2/05_readiness_report.json`).
So one scanner on the server disagrees with another scanner on the same
server. Audit consumers cannot trust the `manifest-state` resource until
this is reconciled.

---

## Impact on consumers

1. **`audit` skill, `implementation-check` workflow** cannot complete its
   `Clause investigation` step (skill Step 4) when any clauses are unknown,
   which is the common case. The required artifact `clause_investigation.json`
   has no producible content under the skill's `evidence_requirements`.

2. **Verdict gating**: `run_implementation_check` returns
   `overall_verdict: partially_compliant` whenever `unknown_clauses` is
   non-empty. Without clause-level investigation, this verdict cannot be
   refined upward to `compliant` or downward to `non_compliant`. Three
   consecutive audit runs on the same repository have terminated at
   `partially_compliant` for this reason alone, despite **zero violated
   clauses** in all three runs.

3. **Skill-level escalation path is missing**: the skill does not document
   a "tool unavailable" branch for Step 4. Auditors either skip the step
   (producing artifacts that don't match the skill's contract) or halt
   the workflow (producing no compliance report at all).

4. **MCP-only consumers** (i.e. callers that cannot fall back to direct
   filesystem reads) cannot retrieve the spec text, intent graph, clause
   matrix, or trace produced by their own `run_implementation_check`
   invocation — they are referenced but not addressable.

## What "fixed" looks like (acceptance criteria)

Each item below maps to one of the symptoms above. They are independent
and can land in any order, but (a) is the most impactful single fix.

### (a) Restore `get_relevant_files` (or an equivalent clause-evidence tool)

Minimum contract (matching the skill's expectation):

- Tool name in `tools/list`: `get_relevant_files`.
- Input: `{"query": "<clause text or natural-language description>"}`.
- Output: list of `{file_path, start_line, end_line, snippet, score}`,
  sorted by score desc.
- Must operate against the graph built by `graph_build`; should return
  an explicit empty list (not error) when the graph is missing or empty,
  so the skill's "If `get_relevant_files` returns empty: run `graph_build`
  first" branch is reachable.
- Source: phase 8 (`llm-sca-tooling-phase-8-repository-query-and-repo-qa-mvp.md`)
  is the natural home if it isn't there already.

### (b) Implement resource handlers for the four URI schemes

`run_implementation_check` already emits these URIs into its report; the
handlers need to follow.

| URI scheme | Handler returns | Notes |
|---|---|---|
| `matrix://impl-check:{run_id}` | Clause-verdict matrix as JSON: `[{clause_id, clause_text, verdict, evidence_refs, confidence}]` | Highest priority — this is the data the auditor needs to classify each unknown. |
| `spec://{doc_id}` | Original spec text (or chunked) + per-chunk hashes | Needed to map clause IDs back to source. |
| `intent-graph://intent:{doc_id}:{intent_id}` | Intent graph nodes and edges for the spec | Useful for clause provenance. |
| `trace://impl-check:{run_id}` | Session trace manifest (tool calls, evidence lookups) | Useful for reproducing the auditor's logic. |

The `04_impl_check_report.json` already references all four URIs by name
(`spec_document_ref`, `intent_graph_ref`, `clause_verdict_matrix_ref`,
`session_trace_manifest_ref`), so the report producer and the resource
consumer are out of sync — fixing the resource side closes the loop.

Source: phase 4 (`llm-sca-tooling-phase-4-mcp-server-core.md`) for
resource registration; phase 14
(`llm-sca-tooling-phase-14-implementation-check-workflow.md`) for the
report's URI emission.

### (c) Register `impl-check:*` run ids in the unified run-record handler

Either route `code-intelligence://runs/impl-check:{x}` to the existing
run-record store, or add an alias: when the resource handler is asked
for `impl-check:{x}`, look it up in whatever store the
implementation-check workflow writes to and return the same shape as
other run records.

Source: phase 4 (resource registration) and phase 14 (run-record
persistence).

### (d) Implement `resources/templates/list`

This is mainly an MCP-conformance fix. The information is already in
`resources/list` for this server, but standards-compliant clients will
try `resources/templates/list` first.

Source: phase 4.

### (e) Reconcile manifest-state with readiness-audit (lower priority)

Two scanners on the same server give opposite answers for the same
artefacts on the same disk. Either:

- align both scanners on a single source of truth (e.g.,
  `readiness_audit`'s scanner), or
- if the `manifest-state` resource is intentionally stale-cached, document
  the TTL and provide a cache-bust knob.

Source: phase 19 (`llm-sca-tooling-phase-19-operational-hardening-and-distribution.md`)
or wherever governance is owned.

---

## Reproduction

From any host with `llm-sca-tooling 0.3.4` installed and the
`research-pipeline` repository at HEAD `242f1342` (or any later HEAD
— the issue is server-side):

```bash
# 1. Drive an end-to-end impl-check
cd /home/grammy-jiang/projects/research-pipeline
uv run python .agent/artifacts/iterative-2/_mcp_client.py \
  .agent/artifacts/iterative-2/_calls_02_main.json

# 2. Probe the resources
uv run python .agent/artifacts/iterative-2/_mcp_client.py \
  .agent/artifacts/iterative-2/_calls_03_probes.json

# 3. Inspect the output — expect:
#    - 00_tools_list.json:  17 tools, no get_relevant_files
#    - 11_matrix_impl-check.json: -32603 Internal error, "No resource handler"
#    - 11_spec_doc.json, 11_intent_graph.json, 11_trace.json: same shape
#    - 11_manifest_state.json: agents_md_present=false despite file existing
```

The client script (`_mcp_client.py`) is a minimal stdio JSON-RPC driver
that speaks the same protocol the `audit` skill prescribes — no Python
imports of `llm_sca_tooling`, no shortcuts. It writes each response to
its own file so the failure modes above are reproducible without
re-running the workflow.

## Cross-reference — three audit runs, same blocker

| Run | Date | Spec | Verdict | Satisfied | Violated | Unknown | Blocker |
|---|---|---|---:|---:|---:|---:|---|
| #1 | 2026-05-13 ~10:20 | `deep-research-system-architecture-design.md` (single doc) | partially_compliant | 924 | 0 | 29 | (a)+(b)+(c) |
| #2 | 2026-05-17 13:43 | `deep-research-system-architecture-design.md` (single doc) | partially_compliant | 924 | 0 | 29 | (a)+(b)+(c)+(d)+(e) |
| #3 | 2026-05-17 17:03 | combined 19-doc spec (17,364 lines) | partially_compliant | 1,823 | 0 | 86 | (a)+(b)+(c)+(d)+(e) |

The codebase under audit moved forward across runs (additional clauses
satisfied as the spec grew; readiness gaps closed). The tooling blockers
did not — they reproduce identically against the same server build.

## Suggested fix ordering

1. **(a)** `get_relevant_files` first — unblocks the largest fraction of
   the skill's evidence requirements on its own.
2. **(b)** `matrix://` handler next — second-largest unblock, directly
   exposes the clause/verdict data the auditor needs.
3. **(c)** `impl-check:*` run-record routing — small but cleans up the
   third evidence path.
4. **(d)** `resources/templates/list` — MCP-conformance hygiene.
5. **(b)** the other three handlers (`spec://`, `intent-graph://`,
   `trace://`) — quality-of-evidence improvements, not strictly needed
   if (a)+(b)+(c) land.
6. **(e)** manifest-state reconciliation — lowest priority because
   `run_readiness_audit` already gives the correct answer.

After (a) lands, a single re-run of the `audit` skill against
`research-pipeline` should be sufficient to confirm the workflow can
satisfy its evidence requirements end-to-end (clause text retrievable,
file:line citations producible, confidence scores assignable).
