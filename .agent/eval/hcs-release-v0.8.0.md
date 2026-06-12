# Harness Condition Sheet — release v0.8.0

## Identification

| Field | Value |
|---|---|
| Run ID | `release:llm-sca-tooling:v0.8.0` |
| Report date | 2026-06-12 |
| Phase / milestone | release v0.8.0 (Tier A gap closure, PR #6) |
| Prepared by | agent (Claude Code), release approved by Grammy Jiang in session |

## Runtime And Model

| Field | Value |
|---|---|
| Runtime name | claude-code |
| Runtime version | 2.1.174 |
| Model backend | claude-fable-5 |
| Model version / API version | claude-fable-5 |
| MCP server name | llm-sca-tooling (code-intelligence) |
| MCP server version | 0.7.0 (session server); release built from 0.8.0 source |

## Manifest State

| Field | Value |
|---|---|
| AGENTS.md revision (git SHA) | 4e57cf1 (last change); repo HEAD d0bac8d |
| CLAUDE.md revision | d0bac8d (repo HEAD) |
| copilot-instructions.md revision | n/a (unchanged) |
| .codex/INSTRUCTIONS.md revision | n/a (unchanged) |
| SKILL.md template(s) active | ship (release workflow) |

## Exposed Tools

| Field | Value |
|---|---|
| Tool set hash | session MCP tools tiers 1–2 (registry @ d0bac8d) |
| Tools active for this run | run_readiness_audit (gates); git/gh/uv/pipx (release mechanics) |
| Tools disabled / unavailable | embedding retrieval in session server (0.7.0 binary; 0.8.0 adds it) |

## Permission Mode

| Field | Value |
|---|---|
| Permission profile | review-commit (release steps; user-approved) |
| Path allowlist | per AGENTS.md § Scope Boundary |
| Network policy | deny-by-default; pypi.org + github.com for lock/push/CI per AGENTS.md |
| Sandbox / devcontainer | host — no sandbox |

## Verification Gates

| Gate | Enabled? | Outcome |
|---|---|---|
| `make verify` | Yes | pass on master @ d0bac8d (pre-bump) and on release commit (recorded below before tag) |
| `uv run isort --check .` | Yes | pass (format phase) |
| `uv run black --check .` | Yes | pass (format phase) |
| `uv run ruff check .` | Yes | pass (format phase) |
| `uv run lint-imports` | Yes | pass |
| `uv run mypy src/` | Yes | pass (379 files, strict) |
| `uv run pytest tests/unit/ -x` | Yes | pass (142 unit + 28 harness) |
| `uv run detect-secrets scan` | Yes | pass (baseline match) |
| `uv run pip-audit` | Yes | pass (no known vulnerabilities) |
| `uv run bandit -r src/` | Yes | pass |
| `local-agent-harness check` | No | skip — not installed; readiness audit provides drift/gate coverage |

| Disabled gate | Justification |
|---|---|
| `local-agent-harness check` | Not installed on host; MCP readiness audit `readiness-audit:tSeslYw_KvnvqaEXKHg3sSxp` (S3, score 22, no drift, no missing gates, no regression vs v0.7.0 audits). Owner: grammy-jiang. Review due: next release. |

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
| Session trace location | `.agent/plan.md` (session log); CI runs recorded below |
| Trace completeness | complete |
| Redaction policy applied | per AGENTS.md; no red-class data observed |

## Evaluation Notes

| Field | Value |
|---|---|
| Known limitations | embedding extra optional — default installs keep null adapter; first embed downloads model (~100 MB); VectorCache unwired (follow-up); Vul4J/HER residuals per v0.7.0 HCS |
| Deviations from standard harness | none beyond waived control above |
| Waived controls | local-agent-harness check (see above) |

## Release Gates (ship skill T1–T4)

| Gate | Outcome |
|---|---|
| Incidents (P0/P1 open) | none — `.agent/incidents/` absent |
| T1 `make verify` | pass (master @ d0bac8d; re-run on release commit before tag) |
| T2 harness regression | pass (28 harness tests inside verify) |
| T3 drift check | pass — `readiness-audit:tSeslYw_KvnvqaEXKHg3sSxp`: drift_findings [], stage S3, score 22 (no per-axis regression) |
| T4 calibration | fail-closed residual (documented evaluation-guide.md); not required at this stage |
| PR CI proof | PR #6: verify + governance green on Node 24 action majors |

## Human Approval (HC3)

| Field | Value |
|---|---|
| Approval for tag + publish | Granted by Grammy Jiang in-session, 2026-06-12: "let's do #1" (= cut v0.8.0, publish, pipx upgrade + inject fastembed) |
| Proposed tag | v0.8.0 |
| Publish targets | GitHub Release (publish.yml) + PyPI via `PYPI_API_TOKEN` |

## Invariants (must hold)

- Positive verdict requires `Trace completeness: complete` — satisfied.
- Waived controls have justification, owner, review date — satisfied.
- Comparability fields filled — satisfied.
