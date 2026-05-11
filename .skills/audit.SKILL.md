---
name: audit
description: Patch-review and implementation-check entrypoint. Use when user says "review this patch", "audit this diff", "should I merge this", "is this PR safe", or "check this implementation against the spec".
metadata:
  version: 0.2.0
---

# Audit (Patch Review / Implementation Check)

## Modes

This skill has two modes:

- **patch-review** — evaluate an unsigned diff via `run_patch_review`.
- **implementation-check** — evaluate an implementation against a Markdown
  specification via `run_implementation_check`.

## When to use
- `review this patch`
- `audit this diff`
- `should I merge this PR`
- `is this change safe`
- `check this implementation against the spec`
- `does the code satisfy the requirements`

## When NOT to use
- The user only wants risk classification without a full report — use `risk_classify` instead.
- The user is asking for fault localisation, not change review.

## Steps
1. Collect the unified diff text and any available SARIF deltas, test results, interface records, run events, and the `run_id` of the originating session — expected outcome: a single `diff` string and optional structured signals.
2. Call `run_patch_review` with the gathered inputs and `sampling_enabled=true` if MCP Sampling is available — expected outcome: a typed `PatchReviewReport` artefact stored under `patch_review/`.
3. Inspect `report.recommendation`. If it is `block` or `review-required`, surface the active deterministic overrides from the embedded `risk_result.active_overrides` and the per-axis `risk_signals` — expected outcome: a faithful explanation grounded in the report.
4. Cite the `harness_condition` (HCS) `hcs_id` and the report `report_id` in any reply — expected outcome: trace-complete answer.

## Verification
- `report.recommendation` is one of `block`, `review-required`, `merge-supporting`, `unknown`.
- Any deterministic override (`sarif_new_critical`, `sarif_new_security`, `failing_required_test`, `out_of_scope_write`, `interface_breaking_change`, `dependency_direction_failed`, `maintainability_block`, `invalid_reproduction_test`, `poc_plus_failed`) MUST flip the recommendation away from `merge-supporting`.
- `report.sampling_used` and `report.fallback_mode` are mutually consistent.

## Stop Conditions
- The diff fails to parse and `report.diagnostics` contains parser errors — stop and ask for a corrected diff.
- `report.recommendation == "unknown"` due to `trace-incomplete` or `budget-exhausted` — stop and ask the user how to proceed; never claim safe-to-merge.
- The agent observes a deterministic override but the response would call the patch `merge-supporting` — abort and re-emit the report verbatim.

## Examples
### Example 1 — clean refactor
User says: `audit this diff` (paste of small refactor with no SARIF deltas)
Actions:
1. Collect diff text only.
2. Call `run_patch_review(diff=...)`.
3. Report recommendation `merge-supporting` with empty `active_overrides`.
Result: report artefact persisted; user sees risk class `safe` with calibration warning when no calibration family is set.

### Example 2 — vulnerability-introducing patch
User says: `review this PR` (paste of diff that triggers a new SARIF critical alert)
Actions:
1. Collect diff and SARIF appeared list.
2. Call `run_patch_review(diff=..., sarif_appeared=[...])`.
3. Report recommendation `block` with override `sarif_new_critical`.
Result: agent never recommends merging.

## Implementation-check mode

### Prerequisites — MANDATORY
1. Call `register_repo(repo_path=<abs_path>)` if not yet registered.
2. Call `graph_build(repo_path=<abs_path>, task=true)` and wait for completion.
   A stale or absent graph causes silent `unknown` verdicts for every clause.

### Steps
1. Collect the Markdown specification text. Optionally collect a `run_id`,
   target `repos`, and policy overrides — expected outcome: a single `spec`
   string and optional structured arguments.
2. **Call `run_implementation_check(spec=..., repos=[...], ...)`** — this is
   the ONLY authoritative method; never substitute manual file reading or a
   general-purpose sub-agent — expected outcome: a typed
   `ImplementationCheckReport` plus `ClauseVerdictMatrix` stored under
   `impl_check/`.
3. Inspect `report.overall_verdict`. If it is `non_compliant` or
   `partially_compliant`, surface the per-clause `violated_clauses` /
   `unknown_clauses` and the dominant evidence recorded in each
   `ClauseVerdictRecord`.
4. **Drilldown on each violated or unknown clause** — for every entry in
   `violated_clauses` and `unknown_clauses`:
   a. Call `answer_repo_question(question=<clause text>, repos=[...])`.
   b. Call `get_graph_slice(repo=..., symbols=[<grounding symbols>])` when
      the clause references specific functions or interfaces.
   c. Summarise the gap with file:line evidence.
5. Cite `report.harness_condition_id` and `report.report_id` in any reply.

### Mandatory prohibitions
- **NEVER** use manual file reads (`view`, `grep`, `glob`, `bash cat`) in place
  of `run_implementation_check`. Name matching is not grounding.
- **NEVER** delegate to a general-purpose sub-agent for manual file inspection.
  Only `run_implementation_check` produces a traceable `ImplementationCheckReport`.
- **NEVER** skip Step 4 (drilldown). Clause identification and evidence
  confirmation are two separate steps.

### Verification
- `report.recommendation` is one of `block`, `review-required`,
  `merge-supporting`, `unknown`.
- Stage 5 violated verdicts MUST flip the recommendation to `block`.
- Security and compliance clauses are never `satisfied` from soft repo-QA
  evidence alone; they remain `unknown` without hard analyser/test evidence.
