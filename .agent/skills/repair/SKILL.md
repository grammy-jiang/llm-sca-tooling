# repair

Private Phase 13 skill for authoring and gating a candidate patch.

Use after `investigate` has produced a ranked fault-localisation report.

## Preconditions

- A bounded context bundle and ranked suspect list from `investigate`.
- At least one failing test or SARIF alert to serve as the acceptance signal.

## Steps

1. Confirm the fault hypothesis using the evidence from `investigate`.
2. Identify the minimal edit surface: functions, lines, or modules to change.
3. Write or extend a failing test that captures the expected behaviour.
4. Author the candidate patch inside the edit scope (`src/`, `tests/`).
5. Run the verify path: formatter → linter → type-check → failing test.
6. Assess patch risk using `classify_patch_risk` and blast radius using `get_graph_slice`.
7. If risk class is HIGH or blast radius crosses critical paths, record rationale and escalate.

## Done

- Failing test now passes; no previously-passing tests regress.
- `classify_patch_risk` verdict is LOW or MEDIUM with recorded rationale.
- Diff is bounded to the declared edit scope.
- Patch is ready for `run_patch_review` before commit.
