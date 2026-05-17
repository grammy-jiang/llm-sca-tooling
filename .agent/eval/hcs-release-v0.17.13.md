# Harness Condition Sheet — Release v0.17.13

---

## Identification

| Field | Value |
|---|---|
| Run ID | `release-v0.17.13` |
| Report date | `2026-05-12` |
| Phase / milestone | `Release v0.17.13 — multi-agent reliability + memory lifecycle gaps` |
| Prepared by | `Copilot CLI (claude-sonnet-4.6)` |

---

## Runtime And Model

| Field | Value |
|---|---|
| Runtime name | `copilot-cli` |
| Runtime version | `1.0.45` |
| Model backend | `claude-sonnet-4.6` |
| Model version / API version | `claude-sonnet-4-6` |
| MCP server name | `code-intelligence (llm-sca-tooling)` |
| MCP server version | `3.2.4` |

---

## Manifest State

| Field | Value |
|---|---|
| AGENTS.md revision (git SHA) | `5710ac0733abf855dd8797046c9adb62eae1e73a` |
| CLAUDE.md revision | `8e455fe` |
| copilot-instructions.md revision | `n/a` |
| .codex/INSTRUCTIONS.md revision | `n/a` |
| SKILL.md template(s) active | `code-audit v1.2.0, release v1.1.0` |

---

## Exposed Tools

| Field | Value |
|---|---|
| Tool set hash | `code-intelligence:3.2.4` |
| Tools active for this run | `register_repo, graph_build, task_status, task_result, run_implementation_check, run_readiness_audit, classify_patch_risk, run_patch_review` |
| Tools disabled / unavailable | `MCP Sampling (fallback_mode=true for patch_review)` |

---

## Permission Mode

| Field | Value |
|---|---|
| Permission profile | `review-commit` |
| Path allowlist | `src/, tests/, .secrets.baseline (per AGENTS.md § Scope Boundary)` |
| Network policy | `deny-by-default; pypi.org and github.com allowed in CI` |
| Sandbox / devcontainer | `host — no sandbox` |

---

## Verification Gates

| Gate | Enabled? | Outcome |
|---|---|---|
| `make verify` | Yes | pass |
| `uv run isort --check .` | Yes | pass (via make verify) |
| `uv run black --check .` | Yes | pass (via make verify) |
| `uv run ruff check .` | Yes | pass |
| `uv run lint-imports` | Yes | pass (via make verify) |
| `uv run mypy src/` | Yes | pass (via make verify) |
| `uv run pytest tests/unit/ -x` | Yes | pass (4442 tests) |
| `uv run detect-secrets scan` | Yes | pass |
| `uv run pip-audit` | Yes | pass — no known vulnerabilities |
| `uv run bandit -r src/` | Yes | pass |
| T2: `uv run pytest tests/harness/ -x` | Yes | pass (27/27, evidence-sca repo) |
| `run_readiness_audit` (MCP) | Yes | pass — S3, score=22, no drift |

| Disabled gate | Justification |
|---|---|
| `local-agent-harness check` | Superseded by `run_readiness_audit` via MCP per release skill |

---

## Context And Cost Policy

| Field | Value |
|---|---|
| Context budget (tokens) | `250,000 hard stop per AGENTS.md` |
| Token spend (actual) | `~180,000 (estimated; no hard stop triggered)` |
| Retry budget (limit) | `3 per tool call` |
| Wall-clock budget (limit) | `30 min warning / 45 min hard stop` |
| Wall-clock actual | `~3:30` |
| Compaction events | `1 (prior checkpoint)` |
| Budget hard stops | `No` |

---

## Telemetry

| Field | Value |
|---|---|
| Session trace location | `/home/grammy-jiang/Documents/evidence-sca/.agent/artifacts/` |
| Trace completeness | `complete` |
| Redaction policy applied | `per AGENTS.md — no red-class data in any artifact` |

Key artifacts:
- `deep_03_all_impl_checks.json` — 1788 satisfied, 0 violated, 82 unknown
- `recheck_gap_spec.json` — 10/10 clauses satisfied post-fix, 0 violated, 0 unknown
- `patch_risk_src_only.json` — process-compliant, review-required
- `patch_review_report_gaps.json` — 0 findings on all 4 axes
- `readiness_report_release.json` — S3, score=22, no drift
- `compliance_report_deep.md` — 5 confirmed gaps identified and fixed
- `patch_verdict.md` — PROCEED verdict with false-positive analysis

---

## Evaluation Notes

| Field | Value |
|---|---|
| Known limitations | `MCP Sampling unavailable; patch_review used fallback_mode=true (single-agent heuristic). classify_patch_risk returned "unknown" due to .secrets.baseline timestamp in diff — src-only diff is process-compliant.` |
| Deviations from standard harness | `classify_patch_risk "unknown" on full diff (see patch_verdict.md for analysis); no T3/T4 (S3 project, not applicable for this patch type)` |
| Waived controls | `none` |

---

## Invariants (must hold)

- A run claiming a positive verdict cannot have `Trace completeness: missing`. ✓ (complete)
- Every waived control must have a reviewed justification with owner and expiry date. ✓ (none waived)
- Two runs are only comparable when runtime, model, manifest revision, and permission
  profile match on their respective HCS.
