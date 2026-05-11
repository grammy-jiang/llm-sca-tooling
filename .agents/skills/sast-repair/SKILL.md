---
name: sast-repair
description: >
  Repair a SAST alert (bandit, ruff security rules) with static-analysis
  re-run verification. Use when a specific SAST finding needs to be fixed or
  suppressed, when `make verify` reports a bandit or ruff `S*` alert, or when
  asked to fix a security lint issue, resolve a bandit finding, or suppress a
  false positive with justification.
compatibility: >
  Requires Python 3.12+, uv, and this repo's development dependencies installed
  (`uv sync`). Run `make verify` before starting to establish a clean baseline.
license: MIT
metadata:
  version: "1.0.0"
---

# sast-repair

## Preconditions

- A specific SAST finding (bandit, ruff `S*` rule, or equivalent) is identified
- Finding ID, file, line number, and severity are documented in `plan.md`
- `make verify` passes on the current branch except for the finding being repaired

## Steps

1. **Reproduce**: `uv run bandit -r src/ -c pyproject.toml` (or `uv run ruff check . --select S`) — confirm the alert is present
2. **Understand root cause**: read the SAST rule documentation; classify as true positive or false positive
3. **True positive** → fix the code to eliminate the unsafe pattern
4. **False positive** → add a targeted inline suppression comment explaining why it is safe; do not use blanket suppression
5. **Re-run SAST** to confirm the finding is resolved
6. **Run tests**: `uv run pytest tests/ -x`
7. **Run full verify**: `make verify`
8. **Update `plan.md`** with decisions log noting true/false positive decision

## Verify Gate

```bash
uv run bandit -r src/ -c pyproject.toml    # target finding gone
uv run ruff check .                         # no new lint findings
make verify                                 # full gate passes
```

## Completion Criteria

- SAST tool no longer reports the original finding
- No new SAST findings were introduced
- For suppressions: inline comment explains why the suppression is safe
- `make verify` exits 0
- PR description identifies finding ID, severity, and true/false positive classification
