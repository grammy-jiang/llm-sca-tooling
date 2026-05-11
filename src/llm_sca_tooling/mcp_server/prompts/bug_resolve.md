# bug-resolve

Arguments: `issue_text` (required), optional `repos`, `budget`.

## Ten-stage workflow

1. **load** — manifest, HarnessConditionSheet, run record.
2. **investigate** — fault localisation + repo-QA; rank suspects.
3. **repair** — generate CandidatePatch (null adapter in Phase 13).
4. **dryrun** — DryRUN prediction; reproduction test draft.
5. **gates** — SARIF, build, test, interface deterministic gates.
6. **patch_risk** — classify_patch_risk; PatchSelectionRecord.
7. **blast_radius** — two-hop caller traversal stub (is_partial: true).
8. **scope_audit** — Phase 11 scope/permission audit.
9. **operational_review** — prior incidents and budget overruns.
10. **trajectory** — record trajectory shape for Phase 17.

## Usage

1. Call `run_issue_resolution(issue_text)` as a task.
2. Poll `task_status` until completed.
3. Call `task_result` to get the `BugResolveReport`.
4. Report: ranked suspects, selected patch, gate results, patch-risk, blast-radius, scope-audit verdict, DryRUN mismatches, remaining-risk notes, HarnessConditionSheet reference, run_id.

## Recommendation rules

- `merge-supporting`: `final_verdict: resolved` AND process-compliant run.
- `review-required`: remaining-risk notes non-empty or `resolved_with_risk`.
- `block`: any hard gate failure, SARIF gate failure, trace-incomplete, budget-exhausted, or process violation.
- `unknown`: insufficient evidence.

Do not claim resolved when any hard gate is blocked. Always include DryRUN mismatches in uncertainty. Preserve `unknown` when evidence is stale or missing.
