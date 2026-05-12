---
name: architecture-compliance
description: >
  Check whether the current codebase fully and correctly implements all features
  and functions defined in a design or architecture document. Use when asked to
  audit implementation completeness against the design doc, check if features or
  functions are fully implemented, verify all architecture requirements are satisfied,
  or investigate with the skills and MCP server. ALWAYS invoke the llm-sca-tooling
  MCP server — never read the architecture doc and write checks manually, never
  use Python imports directly, and never substitute external harness tools.
compatibility: >
  Requires Python 3.12+, uv, and the llm-sca-tooling package installed in the
  current repository. MCP server must be started before any tool calls:
  `uv run llm-sca-tooling mcp serve --transport stdio`
license: MIT
metadata:
  mcp-server: llm-sca-tooling
  mcp-transport: stdio
  version: "1.2.0"
---

# architecture-compliance

> **MANDATORY — DO NOT SKIP:**
> This skill MUST be executed by invoking the `llm-sca-tooling` MCP server and
> calling its tools via JSON-RPC. You MUST NOT:
> - Read the architecture doc and write code checks manually
> - Import Python modules directly as a substitute for MCP tool calls
> - Use `local-agent-harness` or any external tool instead of `run_implementation_check`
>
> Bypassing these steps defeats the purpose of this repository and is a policy violation.

## Workflow Control

Step classification — deterministic steps are executable and exit-code validated;
LLM-reasoning steps require explicit evidence contracts and produce typed artifacts;
the final synthesis step is read-only over prior artifacts.

| Step | ID | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|---|
| Start MCP server | `mcp-init` | deterministic | Yes | — |
| Register repository | `register-repo` | deterministic | Yes | — |
| Build graph index | `graph-build` | deterministic | Yes | `graph_index` (server-side) |
| Run implementation check | `impl-check` | deterministic (MCP-backed) | Yes | `impl_check_report.json` |
| Investigate violated/unknown clauses | `clause-investigation` | llm-reasoning | Yes | `clause_investigation.json` |
| Run readiness audit | `readiness-audit` | deterministic (MCP-backed) | Yes | `readiness_report.json` |
| Emit structured report | `final-report` | final-synthesis (read-only) | — | `compliance_report.md` |

**Failure policy (all steps):** any step that fails blocks downstream steps;
do not proceed to `final-report` unless all prior steps have a `passed` status.

## Artifact Handoff

```
graph_index (server-side)
  -> impl_check_report.json        (satisfied_clauses, violated_clauses, unknown_clauses, overall_verdict)
  -> clause_investigation.json     (per-clause evidence, confidence, file:line references)
  -> readiness_report.json         (per-axis scores, blockers)
  -> compliance_report.md          (final synthesis — read-only from above artifacts)
```

Write all JSON artifacts to `.agent/artifacts/` within the run directory.
Do not advance to `final-report` until all upstream artifacts exist and are valid.

---

## Step 1 — Start the MCP server

```bash
uv run llm-sca-tooling mcp serve --transport stdio
```

Initialize (send on stdin):

```json
{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"agent","version":"1"}},"id":1}
```

**Failure policy:** if server does not respond, stop and report; do not attempt workarounds.

## Step 2 — Register the repository

> **`repo_path` is required** (not `path`, not `repo_id`). Provide an absolute filesystem
> path. The response contains `payload.repo.repo_id` — note it for subsequent `graph_build` calls.

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"register_repo","arguments":{"repo_path":"/absolute/path/to/repo"}},"id":2}
```

## Step 3 — Build graph index (async)

> **`graph_build` requires `repo_path` (absolute path) or `repo_id`** (the ID returned
> by `register_repo` in `payload.repo.repo_id`). **Not** `repo`. This call is async:
> it returns `"status":"accepted"` with a `task_id`. Poll `task_status` until
> `"completed"`, then call `task_result` before proceeding.

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"graph_build","arguments":{"repo_path":"/absolute/path/to/repo"}},"id":3}
```

Poll for completion:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"task_status","arguments":{"task_id":"<task_id>"}},"id":4}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"task_result","arguments":{"task_id":"<task_id>"}},"id":5}
```

## Step 4 — Run implementation check

Pass the FULL content of the architecture document as `spec`:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_implementation_check","arguments":{"spec":"<full_content_of_architecture_doc>"}},"id":6}
```

Read the response:
- `report.satisfied_clauses` — fully implemented
- `report.violated_clauses` — NOT implemented or incorrect
- `report.unknown_clauses` — inconclusive (require manual review)
- `report.overall_verdict` — `compliant` / `partially_compliant` / `non_compliant`

Save the full response as `.agent/artifacts/impl_check_report.json`.
**Failure policy:** overall_verdict of `non_compliant` does not block investigation; proceed to Step 5.

## Step 5 — Investigate violated/unknown clauses

**Step kind:** `llm-reasoning`

```yaml
# LLM reasoning contract for clause-investigation
step_id: clause-investigation
required_inputs:
  - .agent/artifacts/impl_check_report.json      # violated_clauses and unknown_clauses
allowed_tools:
  - run_static_analysis
  - get_relevant_files
  - capture_trace                                  # for unknown clauses only
forbidden_actions:
  - write_files
  - run_tests
  - edit_source
required_output_schema: schemas/evidence.schema.json
evidence_requirements:
  - every violated clause must cite at least one file path and line range
  - every unknown clause must cite retrieved file paths or a trace artifact ID
  - confidence score (0.0–1.0) required for each clause finding
assumption_handling:
  - separate confirmed findings from uncertain inferences
  - uncertain inferences must be labeled assumption: true in output
failure_policy:
  retries: 1
  then: block
```

For each violated or unknown clause, call both:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_static_analysis","arguments":{"repo":"<repo_path_or_id>","predicate":"<clause_text>"}},"id":7}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_relevant_files","arguments":{"repo":"<repo_path_or_id>","query":"<clause_text>"}},"id":8}
```

Save the consolidated results as `.agent/artifacts/clause_investigation.json`.

## Step 6 — Run readiness audit

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"<repo_path_or_id>"}},"id":9}
```

Save the response as `.agent/artifacts/readiness_report.json`.

## Step 7 — Emit structured report

**Step kind:** `final-synthesis` — **read-only over prior artifacts**

> This step MUST NOT introduce findings that are not already present in
> `impl_check_report.json`, `clause_investigation.json`, or `readiness_report.json`.
> All claims in the final report must cite the artifact and field they originate from.

Required report structure:

```markdown
## Verified compliance results
- overall_verdict: <from impl_check_report.json>
- satisfied_clauses: <count and list>

## Confirmed violations
- clause_id: <id>
  evidence: <file:line from clause_investigation.json>
  confidence: <0.0–1.0>

## Assumptions and uncertainties
- clause_id: <id>
  why_uncertain: <reason>

## Readiness blockers
- <from readiness_report.json>
```

Outcomes:
- `compliant` → all features implemented
- `partially_compliant` → list each unimplemented feature with clause ID and file evidence
- `non_compliant` → list all violations with file references

---

## Verify Gate

```
make verify                  # must exit 0
run_implementation_check     # overall_verdict must be "compliant" or "partially_compliant"
run_readiness_audit          # no per-axis regression
```

> **Note:** `partially_compliant` is an accepted verdict when every unimplemented
> clause has file:line evidence in `clause_investigation.json`.  A verdict of
> `non_compliant` or an empty `clause_investigation.json` blocks completion.

## Completion Criteria

- `run_implementation_check` called via MCP JSON-RPC (not Python import)
- `overall_verdict` is `compliant` or `partially_compliant`; for `partially_compliant`,
  every violated/unknown clause must have file:line evidence in `clause_investigation.json`
- Run record exists: `code-intelligence://runs/{run_id}`
- Per-clause verdicts recorded with confidence and provenance
- `clause_investigation.json` exists and every violated/unknown clause has file:line evidence
- `make verify` exits 0
- Final report cites only artifacts from this run (no invented findings)

## Notes

- The MCP tool parameter is `spec` (not `design_ref`)
- Pass the full document text, not a filename
- For `unknown` clauses: use `capture_trace` for dynamic evidence
- See `references/clause-examples.md` for sample clause analysis patterns
- The `register_repo` tool requires `repo_path` (absolute or relative path to the repo
  root), **not** `path`.  A relative `"."` resolves from the server's working directory.
- **Workspace is managed server-side.** Do NOT call `WorkspaceStore.initialize` or any
  other Python module directly — this violates the mandatory constraint above and creates
  a double-nested `.llm-sca/.llm-sca/` artifact.  All tool calls must go through JSON-RPC.
- Architecture documents written in descriptive prose (tables, bullet lists) are
  fully supported by the clause extractor as of v1.2.0.  If `run_implementation_check`
  returns 0 clauses for a valid architecture doc, verify the doc uses Markdown tables or
  bullet items with backtick-delimited symbols.
