---
name: risk-classify
description: Classify a single diff into a risk class via the deterministic patch-risk policy. Use when user says "classify this patch", "what risk class is this diff", "run risk classifier".
metadata:
  version: 0.1.0
---

# Risk Classify

## When to use
- `classify this patch`
- `what risk class is this diff`
- `run patch risk classifier`

## When NOT to use
- The user wants a full review with four-axis findings and HCS — use `audit` instead.
- The user only wants SARIF or test-delta inspection — use the underlying tools directly.

## Steps
1. Collect the unified diff and any structured signals available (SARIF appeared/disappeared, test results before/after, run events, allowlisted paths) — expected outcome: a single `diff` string plus optional signals.
2. Call `classify_patch_risk` with those inputs — expected outcome: a `risk_result` payload containing `risk_class`, `policy_action`, `active_overrides`, `confidence`, and optional `calibrated_probability`.
3. If `risk_result.risk_class == "unknown"`, explicitly flag missing process or calibration evidence to the user — expected outcome: no false confidence.
4. If `risk_result.calibration_family is None`, mention that the calibration gate is not met and the response is deterministic-only — expected outcome: honest confidence reporting.

## Verification
- `risk_result.policy_action` is one of `block`, `review-required`, `merge-supporting`, `unknown`.
- Active overrides are a faithful subset of the recognised override set: `sarif_new_critical`, `sarif_new_security`, `failing_required_test`, `invalid_reproduction_test`, `poc_plus_failed`, `out_of_scope_write`, `interface_breaking_change`, `dependency_direction_failed`, `maintainability_block`, `calibration_family_missing`, `classifier_calibration_below_threshold`.
- When deterministic policy returns `block`, the response NEVER calls the patch safe.

## Stop Conditions
- The diff is empty or unparseable — stop and ask for a valid unified diff.
- `risk_result.risk_class == "unknown"` AND a deterministic block override is active — surface the override; do not attempt to override deterministic policy.

## Examples
### Example 1 — failing required test
User says: `classify this patch`
Actions:
1. Collect diff plus `test_results_before` and `test_results_after`.
2. Call `classify_patch_risk(diff=..., test_results_before=..., test_results_after=..., required_tests=[...])`.
3. Report `risk_class = correct-but-overfit`, `policy_action = block`, override `failing_required_test`.
Result: deterministic block reported faithfully.

### Example 2 — clean change without calibration
User says: `what risk class is this diff`
Actions:
1. Collect diff only.
2. Call `classify_patch_risk(diff=...)`.
3. Report `risk_class = safe`, `policy_action = merge-supporting`, override `calibration_family_missing`, confidence `heuristic`.
Result: user sees deterministic-only verdict with explicit calibration caveat.
