# bug-resolve

Fully-implemented Phase 13 bug-resolve workflow prompt.

## Arguments

- `issue_text` (required): The full text of the issue to resolve.
- `repos` (optional): List of repository identifiers to scope the investigation.
- `budget` (optional): Budget overrides as a JSON object.

## Workflow Overview

The `run_issue_resolution` tool executes a ten-stage deterministic workflow:

1. **load** — load manifest, HarnessConditionSheet, create run record.
2. **investigate** — Phase 9 fault localisation + Phase 8 repo-QA behavioural context.
3. **repair** — generate candidate patch(es) using the `repair` skill template.
4. **dryrun** — generate DryRUN prediction for each candidate.
5. **gates** — deterministic gates: SARIF delta, build/test, interface-contract compatibility.
6. **patch_risk** — Phase 11 patch-risk classification + multi-criterion patch selection.
7. **blast_radius** — blast-radius stub (two-hop traversal).
8. **scope_audit** — Phase 11 scope/permission audit.
9. **operational_review** — pre-check operational compliance from run record.
10. **trajectory** — record trajectory shape for Phase 17.

## Tools Called

- `get_relevant_files` (Phase 9 FL)
- `answer_repo_question` (Phase 8 repo-QA)
- `classify_patch_risk` (Phase 11)
- `run_patch_review` (Phase 11, when `require_patch_review: true`)
- `run_sast_repair` (Phase 12, for SARIF-class issues)

## Evidence Discipline

- `unknown` is preserved when evidence is stale, missing, or ambiguous.
- DryRUN predictions are generated for every candidate; mismatches appear in `BugResolveReport.dryrun_mismatches_ref`.
- Stale graph snapshots are flagged in `BugResolveReport.uncertainty`.

## Recommendations

A `merge-supporting` recommendation requires:
1. Process-compliant run (trace complete, no out-of-scope writes).
2. All hard gates passing (SARIF, build, test, interface).
3. Certificate conclusion: `supported` or `partially_supported` (not `unsupported`).

A `block` recommendation is issued when:
- Any deterministic gate fails.
- Process is non-compliant.
- Budget is exhausted.
- Trace is incomplete.

## Sampling

Sampling is used in the `repair` and `risk-classify` stages when available.
On fallback (no Sampling), the null adapter generates deterministic placeholder
patches for pipeline validation.

## Usage

```
run_issue_resolution(
    issue_text="NullPointerException in UserService.getUser at line 42",
    repos=["myorg/myrepo"],
    budget={"token_budget": 60000}
)
```
