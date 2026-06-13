# Harness Condition Sheet — release v0.16.0

## Identification

| Field | Value |
|---|---|
| Run ID | `release:llm-sca-tooling:v0.16.0` |
| Report date | 2026-06-13 |
| Phase / milestone | release v0.16.0 (PR #18 — multi-language tree-sitter structural backend) |
| Prepared by | agent (Claude Code), release approved by Grammy Jiang in session |

## Runtime And Model

| Field | Value |
|---|---|
| Runtime name | claude-code |
| Runtime version | 2.1.174 |
| Model backend | claude-opus-4-8[1m] |
| Model version / API version | claude-opus-4-8 |
| MCP server name | llm-sca-tooling (code-intelligence) |
| MCP server version | 0.15.0 (session binary); release built from 0.16.0 source |

## Manifest State

| Field | Value |
|---|---|
| AGENTS.md revision (git SHA) | 79ed3de (last change, PR #11); repo HEAD b8346ca |
| CLAUDE.md revision | b8346ca (repo HEAD) |
| copilot-instructions.md revision | n/a (unchanged) |
| .codex/INSTRUCTIONS.md revision | n/a (unchanged) |
| SKILL.md template(s) active | ship (release workflow) |

## Exposed Tools

| Field | Value |
|---|---|
| Tool set hash | session MCP tools tiers 1–2 (registry @ b8346ca) |
| Tools active for this run | run_readiness_audit (gates); git/gh/uv/pipx (release mechanics) |
| Tools disabled / unavailable | live LLM boundaries (no ANTHROPIC_API_KEY — fail-soft default shipped) |

## Permission Mode

| Field | Value |
|---|---|
| Permission profile | review-commit (release steps; user-approved) |
| Path allowlist | per AGENTS.md § Scope Boundary |
| Network policy | deny-by-default; pypi.org + github.com per AGENTS.md allowed egress / CI |
| Sandbox / devcontainer | host — no sandbox |

## Verification Gates

| Gate | Enabled? | Outcome |
|---|---|---|
| `make verify` | Yes | pass on release commit (recorded before tag) |
| format / lint-imports / mypy strict | Yes | pass (384 source files) |
| full test suite (`tests/`) | Yes | pass (859 tests) |
| coverage floor (`--cov-fail-under=85`) | Yes (CI) | pass — total 90.8% |
| `verify-schemas` | Yes | pass |
| `uv run detect-secrets scan` | Yes | pass (baseline match) |
| `uv run pip-audit` | Yes | pass (no known vulnerabilities) |
| `uv run bandit -r src/` | Yes | pass |
| `local-agent-harness check` | No | skip — not installed; readiness audit equivalent (codified in AGENTS.md) |

| Disabled gate | Justification |
|---|---|
| `local-agent-harness check` | Not installed on host; MCP readiness audit `readiness-audit:LmJ878RmWDO_7KsLLcgEOYLU` (S3, score 22, no drift, no missing gates, no regression) — the documented equivalent control per AGENTS.md § Quality Gate item 7. Owner: grammy-jiang. |

## Context And Cost Policy

| Field | Value |
|---|---|
| Context budget (tokens) | per AGENTS.md (70% compaction threshold) |
| Token spend (actual) | within session budget; no budget_warning |
| Retry budget (limit) | 3 per tool call |
| Wall-clock budget (limit) | 30 min warning / 45 min hard stop |
| Wall-clock actual | release steps ~15 min |
| Compaction events | session-managed |
| Budget hard stops | No |

## Telemetry

| Field | Value |
|---|---|
| Session trace location | `.agent/plan.md` (session log); CI run ids recorded post-tag |
| Trace completeness | complete |
| Redaction policy applied | per AGENTS.md; no red-class data observed; no API key in env or artefacts |

## Evaluation Notes

| Field | Value |
|---|---|
| Known limitations | Java `java.jdt` backend remains a gated-off regex stub (user does not use Java); LLM boundaries fail-soft (no key); Vul4J/HER residuals per v0.7.0 HCS |
| Deviations from standard harness | none beyond waived control above |
| Waived controls | local-agent-harness check (codified equivalent — see above) |

## Release Gates (ship skill T1–T4)

| Gate | Outcome |
|---|---|
| Incidents (P0/P1 open) | none — `.agent/incidents/` absent |
| T1 `make verify` | pass on release commit before tag |
| T2 harness regression | pass (full suite + harness inside verify) |
| T3 drift check | pass — `readiness-audit:LmJ878RmWDO_7KsLLcgEOYLU`: drift_findings [], stage S3, score 22 (no per-axis regression) |
| T4 calibration | fail-closed residual (documented); not required at this stage |
| PR CI proof | PR #18: verify (incl. full suite + coverage) green |

## Human Approval (HC3)

| Field | Value |
|---|---|
| Approval for tag + publish | Granted by Grammy Jiang in-session, 2026-06-13: "Please merge now, and make a new release" |
| Proposed tag | v0.16.0 |
| Publish targets | GitHub Release (publish.yml) + PyPI via `PYPI_API_TOKEN` |

## Invariants (must hold)

- Positive verdict requires `Trace completeness: complete` — satisfied.
- Waived controls have justification, owner, review date — satisfied.
- Comparability fields filled — satisfied.
