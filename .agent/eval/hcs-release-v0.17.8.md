# Harness Condition Sheet — research-pipeline v0.17.8

---

## Identification

| Field | Value |
|---|---|
| Run ID | `release:research-pipeline:v0.17.8` |
| Report date | `2026-05-12` |
| Phase / milestone | `release v0.17.8` |
| Prepared by | `Copilot CLI (claude-sonnet-4.6)` |

---

## Runtime And Model

| Field | Value |
|---|---|
| Runtime name | `copilot-cli` |
| Runtime version | `1.0.45` |
| Model backend | `claude-sonnet-4.6` |
| Model version / API version | `claude-sonnet-4.6` |
| MCP server name | `llm-sca-tooling` |
| MCP server version | `0.1.0` |

---

## Manifest State

| Field | Value |
|---|---|
| AGENTS.md revision (git SHA) | `53389d813a58d476bcd133f8d65f84d66fd3479d` |
| CLAUDE.md revision | `n/a` |
| copilot-instructions.md revision | `cab5cbd3b2cfa8229c51cf2380b08e20d5c1bffd` |
| .codex/INSTRUCTIONS.md revision | `n/a` |
| SKILL.md template(s) active | `code-audit v1.2.0, release v1.1.0` |

---

## Exposed Tools

| Field | Value |
|---|---|
| MCP tools active | `register_repo, graph_build, run_implementation_check, run_readiness_audit, classify_patch_risk, run_patch_review, task_status, task_result` |
| Tools disabled / unavailable | `none` |

---

## Permission Mode

| Field | Value |
|---|---|
| Permission mode | `scoped-execute` |
| HC3 approval | `Human-instructed ("make a release")` |
| HC4 migrations | `none` |

---

## Gate Results

### T1 — `make verify`

| Check | Result |
|---|---|
| `ruff format --check` | ✅ pass |
| `ruff check` | ✅ All checks passed |
| `mypy src/` | ✅ pass |
| `pytest tests/unit/` | ✅ 4331 passed, 1 skipped |
| `detect-secrets scan` | ✅ pass |
| `bandit -r src/` | ✅ pass |
| `pip-audit` | ✅ No known vulnerabilities |
| **Exit code** | **0** |

### T2 — Harness regression tests

| Check | Result |
|---|---|
| `tests/harness/` | N/A — directory does not exist in research-pipeline |

### T3 / T4 — Integration / Benchmark

Not applicable at this stage.

---

## Architecture Compliance Audit

| Field | Value |
|---|---|
| Impl-check run ID | `impl-check:impl-check:e80d78dc` |
| Overall verdict | `partially_compliant` (partial graph build artefact) |
| Satisfied clauses | 45 (MCP) + 56 direct |
| Violated clauses | **0** |
| Confirmed gaps fixed | 1 (GAP-001: env var doc name corrected) |
| Readiness audit run ID | `readiness-audit:XIcxtg2XkXvkC13QiKl41h_-` |
| AI readiness score | 22 / S3 |
| Drift findings | 0 |
| Regression blockers | 0 |

---

## Patch Review

| Field | Value |
|---|---|
| Patch diff ID | `diff:69fa6bf49bcd505b` |
| Risk class | `safe` |
| Policy action | `merge-supporting` |
| Classifier | `phase11-deterministic` |
| Static analysis | no new findings |

---

## CI Gate

| Run ID | Status | Jobs |
|---|---|---|
| `25735103794` | ✅ success | Lint+Format, Test 3.12, Test 3.13, Type Check, Security |

---

## Telemetry

| Field | Value |
|---|---|
| Session trace | `.agent/artifacts/` (impl_check_report.json, readiness_report.json, clause_investigation.json, compliance_report.md, patch_risk.json, patch_verdict.md, incident_check.txt) |
| Trace completeness | `complete` |
| Harness condition ID | `hcs:release:research-pipeline:v0.17.8` |

---

## Verdict

**APPROVED for release** — all T1 gates pass, zero violated clauses, CI green,
readiness no regression, patch risk safe, no open incidents.
