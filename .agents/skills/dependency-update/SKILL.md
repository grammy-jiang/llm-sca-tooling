---
name: dependency-update
description: >
  Update a Python dependency with lockfile regeneration, test, SAST, and
  licence checks. Use when asked to update, bump, or upgrade a dependency
  version, when a CVE is reported in a dependency, when `pip-audit` flags a
  vulnerable package, or when asked to keep dependencies current.
compatibility: >
  Requires Python 3.12+, uv, pip-audit, and bandit installed in the dev
  environment (`uv sync`). Run `make verify` before starting.
license: MIT
metadata:
  version: "1.1.0"
---

# dependency-update

## Workflow Control

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Baseline verify | deterministic | Yes | exit code |
| Check changelog | llm-reasoning | No (advisory) | `changelog_analysis.md` |
| Update version constraint | deterministic | Yes | `pyproject.toml` (diff) |
| Regenerate lockfile | deterministic | Yes | `uv.lock` |
| Run test suite | deterministic | Yes | exit code |
| Run dependency audit | deterministic | Yes — block on critical CVE | `pip_audit_report.json` |
| Run SAST | deterministic | Yes — block on high/critical | `bandit_report.json` |
| Check licence compatibility | llm-reasoning | Yes — block on incompatible | `licence_check.md` |
| Update supply-chain ledger | deterministic | Yes | `.agent/eval/supply-chain-ledger.yaml` |
| Run full verify | deterministic | Yes | exit code |

**Failure policy:** any deterministic step failure blocks remaining steps.
LLM-reasoning advisory steps (changelog) do not block; LLM-reasoning gate steps
(licence compatibility) do block if incompatible licence is found.

## Preconditions

- A specific dependency and target version are identified
- `make verify` passes on the current branch before starting
- The update is within the write allowlist (`pyproject.toml`, `uv.lock`)

## Steps

1. **Check changelog** — **LLM-reasoning (advisory)**

   ```yaml
   step_id: changelog-analysis
   required_inputs: [dependency name, current version, target version, public changelog URL]
   allowed_tools: [web_fetch, read_file]
   forbidden_actions: [edit_files, run_commands]
   evidence_requirements:
     - list breaking changes with semver section and description
     - list security fixes with CVE IDs where available
   assumption_handling: separate confirmed changelog facts from inferred implications
   output_artifact: changelog_analysis.md
   failure_policy: {on_no_changelog: warn_and_continue}
   ```

2. **Update version constraint** in `pyproject.toml`

3. **Regenerate lockfile**: `uv lock`

4. **Run test suite**: `uv run pytest tests/ -x`
   **Failure policy:** any test failure blocks Steps 5–10.

5. **Run dependency audit**: `uv run pip-audit --output json > .agent/artifacts/pip_audit_report.json`
   **Failure policy:** any critical CVE blocks Steps 6–10.

6. **Run SAST**: `uv run bandit -r src/ -c pyproject.toml -f json > .agent/artifacts/bandit_report.json`
   **Failure policy:** any high/critical finding blocks Steps 7–10.

7. **Check licence compatibility** — **LLM-reasoning (gate)**

   ```yaml
   step_id: licence-check
   required_inputs: [.agent/artifacts/pip_audit_report.json, dependency name, target version]
   allowed_tools: [web_fetch, read_file]
   forbidden_actions: [edit_files, run_commands]
   evidence_requirements:
     - identify the SPDX licence identifier for the target version
     - confirm compatibility against repo licence (MIT)
     - incompatible licences: GPL, AGPL, SSPL, and other copyleft
   assumption_handling: if licence cannot be confirmed, classify as unknown and block
   output_artifact: licence_check.md
   failure_policy: {on_incompatible: block, on_unknown: block}
   ```

8. **Update supply-chain ledger**: `.agent/eval/supply-chain-ledger.yaml`

9. **Run full verify**: `make verify`

10. **Update `plan.md`** with decisions log

## Verify Gate

```bash
uv run pip-audit
make verify
```

## Completion Criteria

- `uv.lock` updated and committed alongside `pyproject.toml`
- `uv run pip-audit` reports no new critical CVEs
- All tests pass
- Licence compatibility confirmed in `licence_check.md`
- Supply-chain ledger updated with new version, `last_updated_ts`, `dependency_scan_ts`
- PR description notes: dependency name, old version, new version, reason, CVE/licence status
