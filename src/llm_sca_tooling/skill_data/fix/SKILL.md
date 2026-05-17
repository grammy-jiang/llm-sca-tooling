---
name: fix
description: >
  Fix code issues using the right approach for the problem type. Routes to the
  appropriate sub-workflow: SAST alert repair (bandit/ruff security findings),
  test-driven bug repair (write failing test first, then fix), or safe refactor
  (restructure without changing behaviour). Use when asked to fix a SAST/bandit
  finding, fix a bug, repair a defect, refactor, reorganize, clean up, simplify,
  extract functions, rename symbols, or reduce duplication. Also use when
  `make verify` reports a bandit or ruff `S*` alert, or a reproduction script
  exists for a bug.
compatibility: >
  Requires Python 3.12+, uv, and this repo's development dependencies (`uv sync`).
  Run `make verify` before starting to establish a clean baseline.
license: MIT
metadata:
  version: "2.0.0"
---

# fix

## Workflow routing

| User request | Workflow |
|---|---|
| "fix SAST", "fix bandit finding", "fix ruff S*", "suppress false positive" | `sast-repair` |
| "fix bug", "repair defect", "failing test", "regression" | `test-first-repair` |
| "refactor", "reorganize", "clean up", "simplify", "extract", "rename", "reduce duplication" | `safe-refactor` |

---

## Workflow: `sast-repair`

Repair or suppress a SAST finding with static-analysis re-run verification.

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Reproduce finding | deterministic | Yes | `sast_baseline.json` |
| Classify true/false positive | llm-reasoning | Yes | `classification.md` |
| Fix code (true positive) | deterministic (edit) | Yes | code diff |
| Add suppression (false positive) | deterministic (edit) | Yes | code diff |
| Re-run SAST | deterministic | Yes | `sast_post.json` |
| Run tests | deterministic | Yes | exit code |
| Run full verify | deterministic | Yes | exit code |

**1. Reproduce and baseline the finding:**
```bash
uv run bandit -r src/ -c pyproject.toml -f json -o sast_baseline.json
# or for ruff S* rules:
uv run ruff check src/ --select S --output-format json > sast_baseline.json
```

**2. Classify** — LLM reasoning:
- **True positive**: the code is genuinely risky → fix the code.
- **False positive**: the pattern is safe in context → add `# nosec <B-id>` with a comment justifying suppression.

Required evidence: cite the specific file:line and explain why the risk is or is not real.

**3a. Fix code** (true positive):
- Apply the minimal fix that removes the risky pattern.
- Do NOT introduce behaviour changes beyond the SAST fix.

**3b. Add suppression** (false positive):
```python
result = hashlib.sha256(data)  # nosec B324 — sha256 used for non-security content hashing
```
Document justification in `classification.md`.

**4. Re-run SAST** — confirm finding is gone:
```bash
uv run bandit -r src/ -c pyproject.toml -f json -o sast_post.json
```
Compare `sast_post.json` vs `sast_baseline.json`. Block if finding persists.

**5. Run full verify:**
```bash
make verify
```
Must exit 0. No new findings allowed.

**Completion criteria:**
- Finding is absent from `sast_post.json`
- `classification.md` written with true/false positive verdict and evidence
- `make verify` exits 0 with no new findings
- No behaviour changes beyond the SAST fix

---

## Workflow: `test-first-repair`

Fix a bug by writing a failing test before modifying production code (TDD).

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Reproduce bug | deterministic + llm-reasoning | Yes — block if not reproducible | `reproduction.md` |
| Write failing test | deterministic (edit) | Yes | test file diff |
| Confirm only new test fails | deterministic | Yes | `pre_fix_tests.txt` |
| Fix production code | deterministic (edit) | Yes | code diff |
| Run failing test | deterministic | Yes | exit code |
| Run full verify | deterministic | Yes | exit code |

**Failure policy:** if the bug cannot be reproduced with concrete evidence, stop;
do not guess at a fix.

**1. Reproduce:** run the failing test, script, or description. Save evidence in
`reproduction.md` (stack trace, failing assertion, unexpected output).

**2. Write a failing test** that encodes the expected correct behaviour:
```bash
uv run pytest path/to/test_file.py::test_new_case -x  # must FAIL at this point
```

**3. Confirm baseline** — only the new test fails, existing tests still pass:
```bash
uv run pytest tests/ -x --ignore=path/to/new_test.py > pre_fix_tests.txt
# should exit 0
uv run pytest path/to/new_test.py::test_new_case -x
# should exit 1 (the new test is still failing)
```

**4. Fix production code** — minimal change to make the new test pass.

**5. Verify the fix:**
```bash
uv run pytest path/to/test_file.py::test_new_case -x  # must now PASS
make verify                                            # full gate — must exit 0
```

**Completion criteria:**
- `reproduction.md` written with concrete failure evidence
- New test exists and was confirmed failing before the fix
- New test passes after the fix
- All pre-existing tests still pass
- `make verify` exits 0

---

## Workflow: `safe-refactor`

Restructure code without changing observable behaviour.

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Record baseline | deterministic | Yes | `baseline_tests.txt` |
| Declare scope | deterministic | Yes | scope section in plan |
| Apply refactor | deterministic (edit) | Yes — stop on test failure | code diff |
| Run tests (per sub-step) | deterministic | Yes | exit code |
| Run full verify | deterministic | Yes | exit code |
| Confirm behavioural equivalence | deterministic (test-backed) | Yes | exit code |

**Pre-condition:** existing test coverage for the code being refactored is required.
If coverage is absent, write tests first (use `test-first-repair` workflow) before refactoring.

**1. Record baseline:**
```bash
uv run pytest tests/ -x > baseline_tests.txt  # must exit 0
make verify                                    # must exit 0
```

**2. Declare scope** in `.agent/plan.md`: which files/symbols are changing, what
design pattern or structural goal is targeted, what is explicitly out of scope.

**3. Apply refactor incrementally** — after each logical sub-step:
```bash
uv run pytest tests/ -x   # must exit 0 after every sub-step
```
Stop immediately if any test fails; revert that sub-step before continuing.

**4. Run full verify:**
```bash
make verify   # must exit 0
```

**Stop conditions:**
- A test that passed in baseline now fails → revert and stop.
- A new public API is exposed that did not exist before → that is not a refactor; stop.
- External behaviour (outputs, error messages, raised exceptions) changes → stop.

**Completion criteria:**
- `baseline_tests.txt` exists and was captured before any changes
- All tests passing after refactor (same count, same names)
- `make verify` exits 0
- No public API changes, no observable behaviour changes
- Scope declared in plan before editing began
