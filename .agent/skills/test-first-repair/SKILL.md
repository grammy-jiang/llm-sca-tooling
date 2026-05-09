# test-first-repair

Use when fixing a bug.

## Preconditions

- Read the failing behaviour and current tests.
- Add or identify a failing test before editing production code.
- Confirm the change is within the path allowlist.

## Steps

1. Reproduce the failure with the narrowest test command.
2. Add a failing regression test.
3. Implement the smallest production fix.
4. Run the regression test, related tests, and `make verify`.
5. Record verification in `.agent/plan.md`.

## Done

- Regression test fails before the fix and passes after it.
- No unrelated refactor is included.
