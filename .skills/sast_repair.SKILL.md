---
name: sast-repair
description: Repair a single SAST/SARIF alert via the PredicateFix loop. Use when the user says "fix this SARIF alert", "repair this static-analysis finding", "run sast repair", or "repair alert <id>".
metadata:
  version: 0.1.0
---

# SAST Repair

## When to use
- `fix this SARIF alert`
- `repair this static-analysis finding`
- `run sast repair on <alert-id>`
- `propose a patch for <SAST rule>`

## When NOT to use
- The user wants a full bug-resolve workflow with reproduction harness — wait for Phase 13.
- The user wants to mutate the analyser ruleset directly — `evolve_static_rules` is gated and not implemented in Phase 12.
- The user wants free-form code review without a SARIF alert — use `audit` instead.

## Steps
1. Call `get_predicate_examples(rule_id, corpus_root)` for the alert — expected outcome: a typed `examples` list with retrieval method (`predicate_negation`, `rule_family_match`, or `embedding_similarity`).
2. Call `run_sast_repair(alert, corpus_root, ...)` as a task with `null_mode=true` unless an LLM patch generator is configured — expected outcome: a `task_id`, then on completion a `SASTRepairReport`.
3. Read the report fields: `alert_classification`, `predicate_examples`, `sarif_delta`, `build_test_result`, `patch_risk_result`, `remaining_risk_notes`, and `harness_condition_id` — expected outcome: a structured summary that does not paraphrase block conditions away.
4. Map the `verdict` to user-facing language:
   - `alert_fixed` — state the fix; include any `remaining_risk_notes` verbatim.
   - `alert_fixed_with_risk` — state the fix and emit an explicit remaining-risk callout.
   - `repair_failed` — state that the original alert remains; do not claim success.
   - `repair_blocked` — list the new critical/high alerts introduced; flag for review.
   - `false_positive_suppressed` — present the suppression proposal with `reviewer_required: true`.
   - `unknown` — surface the diagnostics; do not invent a verdict.

## Verification
- The response NEVER claims `alert_fixed` while `sarif_delta.original_alert_remains == true`.
- The response NEVER suppresses `sarif_delta.new_critical_or_error_alerts` from the user-visible report.
- All `SuppressionProposal` outputs carry `reviewer_required: true` and are presented as candidates only.
- The `harness_condition_id` and `run_id` are included in the response for operational review.
- `remaining_risk_notes` are included verbatim when non-empty.

## Stop Conditions
- The alert payload is missing `alert_id`, `rule_id`, or a usable location — stop and ask for a properly normalised SARIF alert.
- `evolve_static_rules` is requested as part of the loop — stop; rule mutation is gated and offline-only in Phase 12.
- The corpus adapter cannot find the corpus root — stop and ask for `corpus_root`.

## Examples
### Example 1 — null-mode repair of a nullderef alert
User says: `repair this nullderef alert`
Actions:
1. Call `get_predicate_examples(rule_id="py.nullderef", corpus_root=...)`.
2. Call `run_sast_repair(alert=..., corpus_root=..., null_mode=true)`.
3. Read report; `verdict == "alert_fixed"`, `remaining_risk_notes` empty.
Result: report the fix; include `harness_condition_id` and `run_id`.

### Example 2 — repair blocked by new critical alert
User says: `repair this injection alert`
Actions:
1. Call `get_predicate_examples(rule_id="py.injection.subprocess", corpus_root=...)`.
2. Call `run_sast_repair(...)`; `verdict == "repair_blocked"`.
3. Surface the new critical alert(s) and flag for human review.
Result: no claim of success; reviewer required.

### Example 3 — confirmed false positive
User says: `is this alert a real bug?`
Actions:
1. Call `run_sast_repair(...)` with classification signals indicating test-only symbol and historical suppression.
2. Read `verdict == "false_positive_suppressed"` and `suppression_proposal.reviewer_required == true`.
Result: present the suppression proposal as a reviewer candidate; do not auto-suppress.
