---
name: safe-refactor
description: >
  Restructure code without changing observable behaviour. Use when asked to
  refactor, reorganize, clean up, or simplify code without altering its external
  API, outputs, or error handling. Also use when asked to apply design patterns,
  extract functions, rename symbols, or reduce duplication — as long as no
  behaviour should change.
compatibility: >
  Requires Python 3.12+, uv, and this repo's development dependencies (`uv sync`).
  Existing test coverage for the code being refactored is required. Run
  `make verify` before starting.
license: MIT
metadata:
  version: "1.1.0"
---

# safe-refactor

## Workflow Control

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Record baseline | deterministic | Yes | `baseline_tests.txt` |
| Declare scope | deterministic | Yes | `plan.md` (scope section) |
| Apply refactor | deterministic (edit) | Yes — stop on test failure | code diff |
| Run tests (per sub-step) | deterministic | Yes | exit code |
| Run full verify | deterministic | Yes | exit code |
| Confirm behavioural equivalence | deterministic (test-backed) | Yes | exit code |

**There are no LLM-reasoning steps in this workflow.** All equivalence checks
are test-backed. Do not claim behavioural equivalence without a passing test suite.

**Failure policy:** any test failure during the refactor stops work immediately;
do not continue or suppress failures.

## Preconditions

- Existing tests cover the code being refactored
- `make verify` passes on the current branch before starting
- Scope is explicitly declared in `plan.md` (files and functions to be changed)

## Steps

1. **Record baseline**: run the test suite and capture all passing tests:
   ```bash
   uv run pytest tests/ -v 2>&1 | tee .agent/artifacts/baseline_tests.txt
   ```
   **Failure policy:** if baseline tests fail, stop; do not start refactor.

2. **Declare scope** in `plan.md`: list every file and function that will change.
   Do not expand scope beyond this declaration during the refactor.

3. **Apply the refactor** within the declared scope only.
   Allowed: rename, extract, inline, reorganise, apply design patterns.
   Forbidden: change function signatures, alter error messages, modify log formats,
   change observable outputs, or introduce new public API surface.

4. **Run tests** after each logical sub-step; stop immediately if any test fails.
   **Failure policy:** stop, revert the failing change, and report the specific
   test that failed before proceeding.

5. **Run full verify** (`make verify`) at the end.

6. **Confirm observable behaviour is unchanged**: the test suite passing end-to-end
   with the same set of tests that passed at baseline is the only valid evidence.
   Do not assert equivalence without this evidence.

7. **Update `plan.md`** with decisions log.

## Verify Gate

```bash
make verify
uv run pytest tests/ -x    # all tests that were passing before must still pass
```

## Completion Criteria

- All tests that passed before still pass (`baseline_tests.txt` is the reference)
- `make verify` exits 0
- No new public API surface was introduced
- Scope did not expand beyond what was declared in `plan.md`
- PR description explains the structural change and notes that no observable behaviour was altered
