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
  version: "1.1.0"
---

# test-first-repair

## Workflow Control

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Reproduce bug | deterministic + llm-reasoning | Yes — block if not reproducible | `reproduction.md` |
| Write failing test | deterministic (edit) | Yes | test file diff |
| Confirm only new test fails | deterministic | Yes | `pre_fix_tests.txt` |
| Fix production code | deterministic (edit) | Yes | code diff |
| Run failing test | deterministic | Yes | exit code |
| Run full verify | deterministic | Yes | exit code |

**Failure policy:** if the bug cannot be reproduced with concrete evidence, stop;
do not write a fix without confirmed reproduction evidence.

## Preconditions

- A failing test, bug report, or reproduction script exists
- `make verify` passes on the current branch before starting
- Session plan (`.agent/plan.md`) is written and approved

## Steps

1. **Reproduce** — **mixed: deterministic attempt + llm-reasoning if needed**

   First attempt: run the reproduction script or failing test directly:
   ```bash
   uv run pytest <path_to_failing_test> -x 2>&1 | tee .agent/artifacts/reproduction.txt
   ```

   If no test exists yet, use LLM-reasoning to characterize the bug:
   ```yaml
   step_id: bug-reproduction
   required_inputs:
     - bug report or issue text
     - source files mentioned in the report
   allowed_tools: [read_file, grep, glob]
   forbidden_actions: [edit_files, run_arbitrary_commands]
   evidence_requirements:
     - identify the specific function(s) or code path involved (file:line)
     - describe the actual vs expected behaviour with concrete values
     - confirm the bug is present in the current codebase (not already fixed)
   assumption_handling:
     - separate confirmed findings from inferred paths
     - if the code path cannot be confirmed, label as assumption
   output_artifact: .agent/artifacts/reproduction.md
   failure_policy: {on_not_reproducible: block}
   ```

   Save reproduction evidence as `.agent/artifacts/reproduction.md`.
   **Failure policy:** if the bug cannot be reproduced, stop and report; do not proceed.

2. **Write the failing test**: add a test to `tests/unit/` that fails on the current code.
   - Reference the bug (issue number or description) in the test docstring
   - Keep the test minimal and focused on the single defect
   - The test must fail before the fix and pass after

3. **Run verify**: confirm only the new test fails (all others pass):
   ```bash
   uv run pytest tests/ -v 2>&1 | tee .agent/artifacts/pre_fix_tests.txt
   ```
   **Failure policy:** if any previously passing test now fails, the new test introduces
   a side effect; rewrite it.

4. **Fix the production code** within the write allowlist; do not touch other tests.

5. **Run the failing test** to confirm it now passes:
   ```bash
   uv run pytest tests/unit/<test_file>::<test_function> -x
   ```

6. **Run full verify** (`make verify`) to confirm nothing regressed.

7. **Update `plan.md`** with the decisions log entry.

## Verify Gate

```bash
uv run pytest tests/unit/<test_file>::<test_function> -x    # new test passes
make verify                                                  # full gate passes
```

## Completion Criteria

- `reproduction.md` documents the confirmed bug with file:line evidence
- The new test passes and is committed
- `make verify` exits 0
- No HC violations occurred during the session
- `plan.md` decisions log is updated
- PR description references the failing test and the verified fix
