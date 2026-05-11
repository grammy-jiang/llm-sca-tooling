---
name: impl-check
description: Check whether code fully and comprehensively implements a Markdown specification or plan. Use when user says "does my code match the spec", "check my implementation against the plan", "is this feature fully implemented", "verify this satisfies the requirements", "audit my code against the design doc", or "which parts are missing or incomplete".
metadata:
  version: 0.1.0
---

# Implementation Check

Evaluates whether code fully satisfies every obligation in a Markdown
specification or implementation plan. Returns a per-clause verdict
(`satisfied / violated / unknown`) and an overall recommendation.

## When to use
- `does my code match the spec`
- `check my implementation against the plan`
- `is this feature fully implemented`
- `verify this satisfies the requirements`
- `audit my code against the design doc`
- `which requirements are missing or incomplete`
- `does the implementation cover all the acceptance criteria`
- `check the code against the implementation plan`

## When NOT to use
- You want to review a diff for safety — use `/audit` (patch-review mode) instead.
- You want to find the root cause of a bug — use `/investigate` instead.
- You want a quick merge risk score without full clause analysis — use `/risk-classify` instead.

## What you need to provide
1. **The specification** — paste the Markdown plan, design doc, or acceptance
   criteria directly into the chat, or give the file path.
2. **Optional context** — a `run_id` from a previous indexing session,
   target repo paths, or policy overrides.

## Prerequisites — MANDATORY before calling `run_implementation_check`

> **Skipping these steps makes grounding impossible and the report unreliable.**

1. **Register the repository** — call `register_repo(repo_path=<abs_path>)` if
   the repo has not been registered in this session.
2. **Build / refresh the graph index** — call
   `graph_build(repo_path=<abs_path>, task=true)` and wait for it to complete.
   - If `graph_update` is sufficient (small incremental change), use it instead.
   - Never call `run_implementation_check` with a stale or absent graph: the
     seven-stage DAG requires an up-to-date graph index for grounding.

## Steps
1. Collect the Markdown specification text (and optional `run_id`, repos,
   policy overrides).
2. **Call `run_implementation_check(spec=..., repos=[...], ...)`** — this is
   the ONLY authoritative way to evaluate an implementation against a spec.
   - Pass the full spec text (or read the file and pass its contents as `spec`).
   - Pass `repos` matching the registered repo IDs.
   - Returns an `ImplementationCheckReport` and a `ClauseVerdictMatrix`.
3. Inspect `report.overall_verdict`:
   - `compliant` → recommendation `merge-supporting`; all clauses satisfied.
   - `partially_compliant` → recommendation `review-required`; surface
     `violated_clauses` and `unknown_clauses` with their evidence.
   - `non_compliant` → recommendation `block`; hard Stage-5 violations cannot
     be overridden by soft evidence.
   - `unknown` → not enough evidence; surface ungrounded clauses.
4. **Drilldown on each violated or unknown clause** — for every entry in
   `violated_clauses` and `unknown_clauses`:
   a. Call `answer_repo_question(question=<clause text>, repos=[...])` to
      gather behavioural evidence.
   b. Call `get_graph_slice(repo=..., symbols=[<grounding symbols>])` when the
      clause references specific functions, classes, or interfaces.
   c. Call `get_interface_contract(plugin_id=..., interface_name=...)` when
      the clause is about interface conformance.
   d. Summarise the gap: what is missing, where in the codebase, and what
      evidence confirms the absence.
5. Cite `report.report_id` and `report.harness_condition_id` in the reply.

## How verdicts are decided

| Stage | What it checks |
|---|---|
| Clause extraction | Parses obligation sentences: *must / shall / should / must not* |
| Grounding | Links each clause to symbols, files, or repo-QA evidence |
| Static verdict | Contracts, SARIF alerts, test results, graph-path evidence |
| Soft probes | Repo-QA signals (cannot auto-pass security/compliance clauses) |
| Aggregation | Hard violations dominate; soft consensus for the rest |

## Hard rules
- A Stage-5 (static) violation always stays `violated` — soft evidence
  cannot override it.
- Security and compliance clauses cannot be `satisfied` from soft evidence
  alone; they remain `unknown` without hard analyser/test evidence.
- Every ungrounded clause defaults to `unknown`.

## Mandatory prohibitions — NEVER do these

> Violating any of these makes the audit worthless.

- **NEVER** substitute manual file reading (`view`, `grep`, `glob`, `bash cat`)
  for `run_implementation_check`. Manual reading cannot extract clause
  obligations, run grounding, or produce a `ClauseVerdictMatrix`.
- **NEVER** delegate the audit to a general-purpose sub-agent that does manual
  file inspection. The sub-agent will produce a flat opinion, not a traceable
  `ImplementationCheckReport` with `harness_condition_id`.
- **NEVER** call `run_implementation_check` without first completing the
  Prerequisites section (register + graph_build). A missing or stale graph
  causes silent ungrounded `unknown` verdicts for every clause.
- **NEVER** claim the implementation is complete or gap-free based solely on
  finding a function/class with the right name. Grounding checks the interior
  logic; name matching is not grounding.
- **NEVER** skip the drilldown (Step 4). `run_implementation_check` identifies
  clauses; `answer_repo_question` and `get_graph_slice` confirm the evidence.

## Stop Conditions
- Graph index is absent or clearly stale (last build older than the latest
  commit touching `src/`) — stop, run `graph_build`, then retry.
- `run_implementation_check` returns an error or empty `ClauseVerdictMatrix` —
  stop, surface the diagnostic, and ask whether to retry.
- `report.overall_verdict == "unknown"` with zero grounded clauses — the spec
  text was not parsed correctly or the graph build failed; surface this and ask.

## Example
User says: *"Does the code satisfy the design document at `docs/arch.md`?"*

1. Call `register_repo(repo_path="/abs/path/to/repo")` — expected outcome: repo registered.
2. Call `graph_build(repo_path="/abs/path/to/repo", task=true)` — wait for task completion.
3. Read `docs/arch.md` to obtain the spec text.
4. Call `run_implementation_check(spec="<full arch.md text>", repos=["repo-id"])`.
5. Report returns `partially_compliant` with 2 violated clauses:
   - `must store sessions in Redis` → grounded but no Redis import found (violated)
   - `shall log failed login attempts` → no log call in auth handler (violated)
6. For each violated clause, call `answer_repo_question(question="Is there a Redis import or session store in auth?", repos=["repo-id"])` and `get_graph_slice(repo="repo-id", symbols=["auth_handler"])`.
7. Reply surfaces both violations with file:line evidence from the drilldown; remaining clauses are `satisfied`.
8. Cite `report.report_id` and `report.harness_condition_id`.
