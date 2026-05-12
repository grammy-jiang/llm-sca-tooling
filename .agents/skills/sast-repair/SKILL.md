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
  version: "1.1.0"
---

# sast-repair

## Workflow Control

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Reproduce finding | deterministic | Yes | `sast_baseline.json` |
| Classify true/false positive | llm-reasoning | Yes — block on insufficient evidence | `classification.md` |
| Fix code (true positive) | deterministic (edit) | Yes | code diff |
| Add suppression (false positive) | deterministic (edit) | Yes | code diff |
| Re-run SAST | deterministic | Yes — verify finding is gone | `sast_post.json` |
| Run tests | deterministic | Yes | exit code |
| Run full verify | deterministic | Yes | exit code |

**Failure policy:** any deterministic step failure blocks downstream steps.
The classification step blocks if the required evidence cannot be gathered.

## Preconditions

- A specific SAST finding (bandit, ruff `S*` rule, or equivalent) is identified
- Finding ID, file, line number, and severity are documented in `plan.md`
- `make verify` passes on the current branch except for the finding being repaired

## Steps

1. **Reproduce**: run SAST and confirm the alert is present; save output as `sast_baseline.json`:
   ```bash
   uv run bandit -r src/ -c pyproject.toml -f json > .agent/artifacts/sast_baseline.json
   # or: uv run ruff check . --select S --output-format json > .agent/artifacts/sast_baseline.json
   ```
   **Failure policy:** if finding is not present, stop; the precondition is not met.

2. **Classify true/false positive** — **LLM-reasoning (gate)**

   ```yaml
   step_id: sast-classification
   required_inputs:
     - .agent/artifacts/sast_baseline.json      # finding ID, file, line, message
     - source file at the flagged location       # read the code
     - SAST rule documentation                   # understand the rule intent
   allowed_tools: [read_file, web_fetch]
   forbidden_actions: [edit_files, run_commands]
   evidence_requirements:
     - cite the specific code pattern that triggers the rule (file:line)
     - cite the rule documentation explaining the security concern
     - for false positive: cite concrete reason the pattern is safe in this context
     - confidence score required (0.0–1.0)
   assumption_handling:
     - if safety cannot be confirmed, default to true_positive
     - assumptions must be labeled separately from confirmed findings
   output_artifact: .agent/artifacts/classification.md
   output_structure:
     verdict: true_positive | false_positive
     evidence: <cited code location and rule doc>
     confidence: <0.0-1.0>
     reasoning: <confirmed facts and labeled assumptions>
   failure_policy: {on_insufficient_evidence: classify_as_true_positive}
   ```

3. **True positive** → fix the code to eliminate the unsafe pattern.
   Do not use suppression comments for true positives.

4. **False positive** → add a targeted inline suppression comment.
   The comment must include: why the pattern is safe, the rule ID, and the confidence score.
   Do not use blanket suppression (`# noqa` without rule ID, `# nosec` without reason).

5. **Re-run SAST** to confirm the finding is resolved; save as `sast_post.json`:
   ```bash
   uv run bandit -r src/ -c pyproject.toml -f json > .agent/artifacts/sast_post.json
   ```
   **Failure policy:** if the original finding is still present, stop and re-examine.

6. **Run tests**: `uv run pytest tests/ -x`

7. **Run full verify**: `make verify`

8. **Update `plan.md`** with decisions log noting true/false positive decision and evidence

## Verify Gate

```bash
uv run bandit -r src/ -c pyproject.toml    # target finding gone
uv run ruff check .                         # no new lint findings
make verify                                 # full gate passes
```

## Completion Criteria

- SAST tool no longer reports the original finding
- No new SAST findings were introduced
- `classification.md` records the true/false positive verdict with cited evidence
- For suppressions: inline comment explains why the suppression is safe, includes rule ID
- `make verify` exits 0
- PR description identifies finding ID, severity, and true/false positive classification
