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
  version: "1.0.0"
---

# safe-refactor

## Preconditions

- Existing tests cover the code being refactored
- `make verify` passes on the current branch before starting
- Scope is explicitly declared in `plan.md` (files and functions to be changed)

## Steps

1. **Record baseline**: run the test suite and note all passing tests
2. **Declare scope** in `plan.md`: list every file and function that will change
3. **Apply the refactor** within the declared scope only
4. **Run tests** after each logical sub-step; stop immediately if any test fails
5. **Run full verify** (`make verify`) at the end
6. **Confirm observable behaviour is unchanged**: outputs, API contracts, error messages, and log formats must be identical before and after
7. **Update `plan.md`** with decisions log

## Verify Gate

```bash
make verify
uv run pytest tests/ -x    # all tests that were passing before must still pass
```

## Completion Criteria

- All tests that passed before still pass
- `make verify` exits 0
- No new public API surface was introduced
- Scope did not expand beyond what was declared in `plan.md`
- PR description explains the structural change and notes that no observable behaviour was altered
