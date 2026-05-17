---
name: ship
description: >
  Prepare code to ship: update a dependency, run an evaluation/benchmark, or
  cut a versioned release with full gating. Use when asked to update, bump, or
  upgrade a dependency version, when a CVE is reported in a dependency, when
  `pip-audit` flags a vulnerable package, when asked to run benchmarks or record
  an evaluation run, assess AI-readiness, or when asked to prepare a release, cut
  a release, bump a version for publication, or tag a release. Requires explicit
  human approval for git tag and publish (HC3 — destructive operation).
  Uses the llm-sca-tooling MCP server for readiness and drift checks.
compatibility: >
  Requires Python 3.12+, uv, pip-audit, and bandit installed (`uv sync`).
  For evaluation and release workflows, the llm-sca-tooling MCP server is needed:
  `uv run llm-sca-tooling mcp serve --transport stdio`
  HCS template at `.agent/templates/harness-condition-sheet.md`.
  All T1–T4 gates must pass for release. No open P0/P1 incidents allowed.
license: MIT
metadata:
  mcp-server: llm-sca-tooling
  mcp-transport: stdio
  version: "2.0.0"
---

# ship

## Workflow routing

| User request | Workflow |
|---|---|
| "update dependency", "bump package", "CVE in dependency", "pip-audit finding" | `dependency-update` |
| "run benchmarks", "evaluate tooling", "record HCS", "assess readiness" | `evaluation` |
| "prepare release", "cut release", "bump version", "tag release" | `release` |

---

## Workflow: `dependency-update`

Update a Python dependency with lockfile regeneration, test, SAST, and licence checks.

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Baseline verify | deterministic | Yes | exit code |
| Check changelog | llm-reasoning | No (advisory) | `changelog_analysis.md` |
| Update version constraint | deterministic | Yes | `pyproject.toml` diff |
| Regenerate lockfile | deterministic | Yes | `uv.lock` |
| Run test suite | deterministic | Yes | exit code |
| Run dependency audit | deterministic | Yes — block on critical CVE | `pip_audit_report.json` |
| Run SAST | deterministic | Yes — block on high/critical | `bandit_report.json` |
| Check licence compatibility | llm-reasoning | Yes — block on incompatible | `licence_check.md` |
| Update supply-chain ledger | deterministic | Yes | `.agent/eval/supply-chain-ledger.yaml` |

**1. Baseline verify:**
```bash
make verify   # must exit 0 before any change
```

**2. Check changelog** — read the release notes between current and target version.
Save advisory notes in `changelog_analysis.md`. Flag any breaking changes.

**3. Update version constraint** in `pyproject.toml`:
```bash
# Edit pyproject.toml: change "<package>>=X.Y" to target version
```

**4. Regenerate lockfile:**
```bash
uv lock
```

**5. Run test suite:**
```bash
uv run pytest tests/ -x
```

**6. Run dependency audit:**
```bash
uv run pip-audit --format json -o pip_audit_report.json
```
Block if any critical CVE is present. Document findings in plan.

**7. Run SAST:**
```bash
uv run bandit -r src/ -c pyproject.toml -f json -o bandit_report.json
```
Block on any new high/critical finding introduced by the update.

**8. Check licence compatibility** — verify the new version's licence is
compatible with the project's licence (MIT). Save verdict in `licence_check.md`.

**9. Update supply-chain ledger** (`.agent/eval/supply-chain-ledger.yaml`):
```yaml
- package: <name>
  old_version: <x.y.z>
  new_version: <a.b.c>
  cve_cleared: <true|false>
  updated_at: <ISO-8601>
  approved_by: <agent|human>
```

**Completion criteria:**
- `make verify` exits 0 after update
- No critical CVEs in `pip_audit_report.json`
- No new high/critical SAST findings in `bandit_report.json`
- Licence compatibility confirmed
- Supply-chain ledger updated

---

## Workflow: `evaluation`

Run a benchmark or regression suite and record a Harness Condition Sheet (HCS).

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Copy and start HCS | deterministic | Yes | `hcs-<run_id>.md` |
| Run evaluation suite | deterministic | Yes — block on failure | benchmark results |
| Record raw results in HCS | deterministic | Yes | `hcs-<run_id>.md` (updated) |
| Write session trace | deterministic | Yes — block if trace missing | `trace.jsonl` |
| Run full verify | deterministic | Yes | exit code |
| Run readiness audit (MCP) | deterministic (MCP-backed) | Yes — block on regression | `readiness_report.json` |

**1. Copy HCS template:**
```bash
cp .agent/templates/harness-condition-sheet.md .agent/eval/hcs-$(date +%Y%m%d-%H%M).md
```
Fill in `run_id`, `session_id`, `workflow`, `trigger` fields.

**2. Run evaluation suite:**
```bash
uv run pytest tests/harness/ -x
# or the specific benchmark command for this project
```
Record pass/fail and all metric values in the HCS.

**3. Write session trace** to `.agent/eval/trace-<run_id>.jsonl` — required;
block if trace cannot be written.

**4. Run full verify:**
```bash
make verify   # must exit 0
```

**5. Run readiness audit (MCP):**
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"<repo_path_or_id>"}},"id":2}
```
Block if any per-axis score regresses vs the previous audit. Save as `readiness_report.json`.

**6. Complete HCS** — fill in all remaining fields including `harness_condition_id`.

**Completion criteria:**
- HCS fully filled and saved to `.agent/eval/`
- Session trace file exists
- `readiness_report.json` shows no per-axis regression
- `make verify` exits 0
- No red-class data in any artefact

---

## Workflow: `release`

Prepare and gate a package release with T1–T4 evaluation, readiness checks,
and incident verification.

**⚠️ HC3:** git tag and package publish require **explicit human approval** before execution.

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Check incident log | deterministic | Yes — block on open P0/P1 | `incident_check.txt` |
| Run readiness audit (MCP) | deterministic (MCP-backed) | Yes — block on regression | `readiness_report.json` |
| Copy and fill HCS | deterministic | Yes | `hcs-release-<version>.md` |
| T1: `make verify` | deterministic | Yes | exit code |
| T2: harness regression tests | deterministic | Yes | exit code |
| T3: drift check (MCP) | deterministic (MCP-backed) | Yes — block on relaxed drift | `drift_report.json` |
| T4: adversarial / calibration checks | deterministic | Yes (if required) | results |
| Bump version | deterministic | Yes | `pyproject.toml` diff |
| Build wheel | deterministic | Yes | `dist/` |
| **Human approval** | human gate (HC3) | Yes — required | approval recorded |
| Git tag + publish | destructive (HC3) | Yes | tag + PyPI entry |

**1. Check incident log:**
```bash
ls .agent/incidents/ 2>/dev/null || echo "no incidents"
```
Block if any P0 or P1 incident is open (not marked `resolved`).

**2. Run readiness audit (MCP):**
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"<repo_path_or_id>"}},"id":2}
```
Save as `readiness_report.json`. Block on any per-axis regression or relaxed drift.

**3. Copy and fill HCS template:**
```bash
cp .agent/templates/harness-condition-sheet.md .agent/eval/hcs-release-<version>.md
```

**4. T1 — `make verify`:**
```bash
make verify   # must exit 0
```

**5. T2 — harness regression tests:**
```bash
uv run pytest tests/harness/ -x
```

**6. T3 — drift check (MCP):**
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"classify_harness_drift","arguments":{"repo":"<repo_path_or_id>"}},"id":3}
```
Block on `relaxed` drift class. Save as `drift_report.json`.

**7. T4 — adversarial/calibration** (if required by HCS):
Run as specified in the HCS template for the current stage.

**8. Bump version** in `pyproject.toml` (e.g., `version = "0.3.0"`).

**9. Build wheel:**
```bash
uv build --wheel
```

**10. ⚠️ Request human approval (HC3)** — present summary of:
- HCS reference and `harness_condition_id`
- All gate results (T1–T4)
- Readiness report summary
- Drift report verdict
- Proposed tag name and publish target

**Do NOT proceed to step 11 without explicit human approval.**

**11. Git tag + publish** (only after human approval):
```bash
git tag v<version>
git push origin v<version>
uv publish          # or: twine upload dist/*
```

**Completion criteria:**
- No open P0/P1 incidents
- All T1–T4 gates passed
- HCS fully filled with `harness_condition_id`
- Readiness report: no per-axis regression
- Drift report: no relaxed drift
- Human approval recorded in HCS before tag/publish
- Session trace file exists
- `make verify` exits 0
