# SKILL: sast-repair

Repair a SAST alert with static analysis re-run verification.

---

## Preconditions

- A specific SAST finding (bandit, ruff `S*` rule, or equivalent) is identified.
- The finding ID, file, line number, and severity are documented in plan.md.
- `make verify` passes on the current branch except for the finding being repaired.

---

## Steps

1. **Reproduce the finding**: run `uv run bandit -r src/ -c pyproject.toml` (or
   `uv run ruff check . --select S`) and confirm the alert is present.
2. **Understand the root cause**: read the SAST rule documentation; confirm whether
   the alert is a true positive or a false positive.
3. **For a true positive**: fix the code to eliminate the unsafe pattern.
4. **For a false positive**: add a targeted suppression with an inline comment
   explaining why it is safe; do not use blanket suppression.
5. **Re-run the SAST tool** to confirm the finding is resolved.
6. **Run the test suite** to confirm nothing regressed.
7. **Run full verify**: `make verify`.
8. **Update plan.md** with decisions log noting true/false positive decision.

---

## Verify Gate

```
uv run bandit -r src/ -c pyproject.toml    # target finding gone
uv run ruff check .                         # no new lint findings
make verify                                 # full gate passes
```

---

## Completion Criteria

- The SAST tool no longer reports the original finding.
- No new SAST findings were introduced.
- For suppressions: an inline comment explains why the suppression is safe.
- `make verify` exits 0.
- PR description identifies the finding ID, severity, and whether it was a true
  or false positive.
