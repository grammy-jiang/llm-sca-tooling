# Repair

Private Phase 13 repair workflow template.

Use `run_issue_resolution` after fault-localisation candidates have been
assembled. The repair workflow requires:
1. A normalised issue text with symptoms, expected/observed behaviour,
   and ranked file candidates from Phase 9 `get_relevant_files`.
2. A bounded context bundle with graph slice, SARIF evidence, and blame chain.
3. A patch candidate that modifies only files in the ranked candidate list.
4. A dryrun gate result confirming no new SARIF findings are introduced.

Do not apply patches without a passing dryrun and a Harness Condition Sheet.
