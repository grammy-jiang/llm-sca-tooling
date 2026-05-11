# SKILL: test-first-repair

Fix a bug by writing a failing test before modifying production code.

---

## Preconditions

- A failing test, bug report, or reproduction script exists.
- `make verify` passes on the current branch before starting.
- Session plan (`.agent/plan.md`) is written and approved.

---

## Steps

1. **Reproduce**: confirm the bug is reproducible; document the reproduction in plan.md.
2. **Write the failing test**: add a test to `tests/unit/` that fails on the current code.
   The test must:
   - Reference the bug (issue number or description) in its docstring.
   - Be minimal and focused on the single defect.
3. **Run verify** to confirm only the new test fails (all others pass).
4. **Fix the production code** within the write allowlist; do not touch other tests.
5. **Run the failing test** to confirm it now passes.
6. **Run full verify** (`make verify`) to confirm nothing regressed.
7. **Update plan.md** with the decisions log entry.

---

## Verify Gate

```
uv run pytest tests/unit/<test_file>::<test_function> -x    # new test passes
make verify                                                  # full gate passes
```

---

## Completion Criteria

- The new test passes and is committed.
- `make verify` exits 0.
- No HC violations occurred during the session.
- Plan.md decisions log is updated.
- PR description references the failing test and the verified fix.
