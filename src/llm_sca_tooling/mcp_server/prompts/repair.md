# repair

Entry: `repair(investigate_result, candidate_index?, issue_context?)`.

1. Load the graph slice for the top fault locations.
2. Check cross-language interface contracts for each changed symbol (Phase 7).
3. If the issue maps to a SARIF alert: call `run_sast_repair(alert_id)`.
4. Otherwise: generate a unified diff patch from graph slice and summaries.
5. Generate pre/postconditions for changed functions.
6. Generate reproduction test draft (assertflip when issue contains clear observable failure).
7. Generate execution-free certificate.
8. Return CandidatePatch with all artefact references.

Rules:
- Load bounded source spans only when evidence model indicates exact code is needed.
- Never generate patches that write to files outside the changed-symbols scope.
- Template snapshot must be stable.
- remaining-risk notes are required for vulnerability-class patches without PoC+.
