# SKILL: safe-refactor

Restructure code without changing observable behaviour.

---

## Preconditions

- Existing tests cover the code being refactored.
- `make verify` passes on the current branch before starting.
- Scope is explicitly declared in plan.md (files and functions to be changed).

---

## Steps

1. **Record baseline**: run the test suite and note all passing tests.
2. **Declare scope** in plan.md: list every file and function that will change.
3. **Apply the refactor** within the declared scope only.
4. **Run tests** after each logical sub-step; stop immediately if any test fails.
5. **Run full verify** (`make verify`) at the end.
6. **Confirm observable behaviour is unchanged**: outputs, API contracts, error
   messages, and log formats must be identical before and after.
7. **Update plan.md** with decisions log.

---

## Verify Gate

```
make verify
uv run pytest tests/ -x    # all tests that were passing before must still pass
```

---

## Completion Criteria

- All tests that passed before still pass.
- `make verify` exits 0.
- No new public API surface was introduced.
- Scope did not expand beyond what was declared in plan.md.
- PR description explains the structural change and notes that no observable
  behaviour was altered.
