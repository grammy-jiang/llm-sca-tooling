---
name: test-first-repair
description: >
  Fix a bug by writing a failing test before modifying production code (test-driven
  bug repair). Use when asked to fix a bug, resolve a failing test, repair a defect,
  or when a reproduction script exists and a systematic TDD approach should be used.
  Also use when a regression must be prevented by pinning the fix with a test.
compatibility: >
  Requires Python 3.12+, uv, and this repo's development dependencies (`uv sync`).
  A failing test, bug report, or reproduction script must exist. Run `make verify`
  before starting to confirm a clean baseline.
license: MIT
metadata:
  version: "1.0.0"
---

# test-first-repair

## Preconditions

- A failing test, bug report, or reproduction script exists
- `make verify` passes on the current branch before starting
- Session plan (`.agent/plan.md`) is written and approved

## Steps

1. **Reproduce**: confirm the bug is reproducible; document the reproduction in `plan.md`
2. **Write the failing test**: add a test to `tests/unit/` that fails on the current code
   - Reference the bug (issue number or description) in the test docstring
   - Keep the test minimal and focused on the single defect
3. **Run verify**: confirm only the new test fails (all others pass)
4. **Fix the production code** within the write allowlist; do not touch other tests
5. **Run the failing test** to confirm it now passes
6. **Run full verify** (`make verify`) to confirm nothing regressed
7. **Update `plan.md`** with the decisions log entry

## Verify Gate

```bash
uv run pytest tests/unit/<test_file>::<test_function> -x    # new test passes
make verify                                                  # full gate passes
```

## Completion Criteria

- The new test passes and is committed
- `make verify` exits 0
- No HC violations occurred during the session
- `plan.md` decisions log is updated
- PR description references the failing test and the verified fix
