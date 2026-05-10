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

## Steps
1. Collect the Markdown specification text (and optional `run_id`, repos,
   policy overrides).
2. Call `run_implementation_check(spec=..., ...)` — returns an
   `ImplementationCheckReport` and a `ClauseVerdictMatrix`.
3. Inspect `report.overall_verdict`:
   - `compliant` → recommendation `merge-supporting`; all clauses satisfied.
   - `partially_compliant` → recommendation `review-required`; surface
     `violated_clauses` and `unknown_clauses` with their evidence.
   - `non_compliant` → recommendation `block`; hard Stage-5 violations cannot
     be overridden by soft evidence.
   - `unknown` → not enough evidence; surface ungrounded clauses.
4. Cite `report.report_id` and `report.harness_condition_id` in the reply.

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

## Example
User says: *"Here's my implementation plan for the authentication module —
does the code satisfy it?"* (pastes Markdown plan)

1. Call `run_implementation_check(spec="... pasted plan ...")`.
2. Report returns `partially_compliant` with 2 violated clauses:
   - `must store sessions in Redis` → grounded but no Redis import found (violated)
   - `shall log failed login attempts` → no log call in auth handler (violated)
3. Reply surfaces both violations with file/symbol evidence; remaining
   clauses are `satisfied`.
