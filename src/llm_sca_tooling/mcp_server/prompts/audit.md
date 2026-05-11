# audit

Two modes: `patch` and `implementation_check`.

---

## audit patch mode

Use `audit(mode="patch", diff="<unified diff>")`.

1. Call `run_patch_review(diff)` as a task.
2. Poll to completion.
3. Read correctness, security, performance, and compatibility findings.
4. Highlight new/disappeared SARIF alerts.
5. Report every DryRUN mismatch.
6. Report scope-audit process violations.
7. Report maintainability-gate findings.
8. Summarise patch-risk class and evidence.
9. State `merge-supporting`, `review-required`, `block`, or `unknown`.
10. Include the Harness Condition Sheet reference.

Never claim `merge-supporting` when a deterministic block condition is active.

---

## audit implementation-check mode

Use `audit(mode="implementation_check", content="<spec or design text>")`.

1. Call `run_implementation_check(spec)` as a task.
2. Poll to completion.
3. Read the `ClauseVerdictMatrix`.
4. For each `violated` clause: state the evidence and which predicate/test fired.
5. For each `unknown` clause: state what evidence is missing.
6. For security and harness-policy clauses: highlight explicitly.
7. State the overall compliance verdict.
8. State any manifest regression findings that contributed to `violated` verdicts.
9. Include `HarnessConditionSheet` reference and `run_id` for operational review.

Rules:
- Never claim `compliant` when any clause is `violated`.
- List all `violated` clauses explicitly.
- Do not suppress `unknown` clauses for security or harness-policy categories.
- `violated` from Stage 5 dominates all soft evidence unconditionally.
- `unknown` is preserved whenever evidence is missing or grounding failed.
