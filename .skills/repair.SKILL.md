---
name: repair
description: Phase 13 repair stage skill — generate a candidate patch with pre/postcondition draft, reproduction test, and execution-free certificate. Use when the bug-resolve workflow enters the `repair` stage.
metadata:
  version: 0.1.0
---

# repair

Private skill template for the repair stage of the bug-resolve workflow.

## Entry

`repair(investigate_result, candidate_index?, issue_context?)`

## Instructions

1. Load the graph slice for the top fault locations from
   `InvestigateResult.ranked_candidates`.
2. Check for cross-language interface contracts that the symbol participates in
   (Phase 7).
3. If the issue maps to a SARIF alert:
   a. Call `run_sast_repair` to generate the SARIF-guided patch.
   b. Validate the output against the SARIF rule.
4. Otherwise:
   a. Generate a patch in unified diff format using the graph slice and
      summaries.
   b. Load bounded source spans only when the evidence model indicates exact
      code is needed.
5. Generate pre/postconditions for changed functions.
6. Generate reproduction test draft:
   - Use `assertflip` pattern when the issue describes a clear observable
     failure.
   - Keep the test separate from production changes until hard-evidence
     criteria are met.
7. Generate execution-free certificate from graph/SARIF evidence.
8. Return `CandidatePatch` with artefact references for all generated artefacts.

## Rules

- Patches must be valid unified diffs before proceeding to gates.
- Never generate patches that write outside the changed-symbols scope.
- Source files are included only when the evidence model says exact code is
  needed.

## Mandatory prohibitions
- **NEVER** generate a patch from manual file reading alone without first
  obtaining `ranked_candidates` from the `investigate` stage.
- **NEVER** skip `run_sast_repair` when the issue maps to a SARIF alert;
  free-form patching of SARIF alerts is not traceable and bypasses the
  `harness_condition_id` chain.
- **NEVER** claim the patch is ready until `CandidatePatch.pre_postconditions`
  and the reproduction test draft are both present.
