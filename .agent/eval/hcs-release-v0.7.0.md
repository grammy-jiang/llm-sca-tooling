# Harness Condition Sheet — release v0.7.0

## Identification

| Field | Value |
|---|---|
| Run ID | `release:llm-sca-tooling:v0.7.0` |
| Report date | 2026-06-12 |
| Phase / milestone | release v0.7.0 (gap-closure release after 2026-06-12 completeness audit) |
| Prepared by | agent (Claude Code), release approved by Grammy Jiang in session |

## Runtime And Model

| Field | Value |
|---|---|
| Runtime name | claude-code |
| Runtime version | 2.1.174 |
| Model backend | claude-fable-5 |
| Model version / API version | claude-fable-5 |
| MCP server name | llm-sca-tooling (code-intelligence) |
| MCP server version | 0.6.3 (session server); release built from 0.7.0 source |

## Manifest State

| Field | Value |
|---|---|
| AGENTS.md revision (git SHA) | 4e57cf1 (last change), repo HEAD 92e4179 |
| CLAUDE.md revision | 92e4179 (repo HEAD) |
| copilot-instructions.md revision | n/a (unchanged this session) |
| .codex/INSTRUCTIONS.md revision | n/a (unchanged this session) |
| SKILL.md template(s) active | audit, fix, ship |

## Exposed Tools

| Field | Value |
|---|---|
| Tool set hash | session MCP tools tiers 1–2 (see `mcp_server/tools.py` registry @ 92e4179) |
| Tools active for this run | register_repo, graph_build, task_status, task_result, run_implementation_check, run_readiness_audit, get_relevant_files, run_operational_review |
| Tools disabled / unavailable | embedding retrieval (fastembed not installed — Phase 9 optional) |

## Permission Mode

| Field | Value |
|---|---|
| Permission profile | scoped-execute → review-commit (release steps) |
| Path allowlist | per AGENTS.md § Scope Boundary |
| Network policy | deny-by-default; pypi.org + github.com used for dependency resolution, push, and CI per AGENTS.md allowed egress |
| Sandbox / devcontainer | host — no sandbox |

## Verification Gates

| Gate | Enabled? | Outcome |
|---|---|---|
| `make verify` | Yes | pass (see plan.md Verification; re-run on master pre-tag) |
| `uv run isort --check .` | Yes | pass (verify-format phase) |
| `uv run black --check .` | Yes | pass (verify-format phase) |
| `uv run ruff check .` | Yes | pass (verify-format phase) |
| `uv run lint-imports` | Yes | pass |
| `uv run mypy src/` | Yes | pass (377 files, strict) |
| `uv run pytest tests/unit/ -x` | Yes | pass (142 unit + 28 harness) |
| `uv run detect-secrets scan` | Yes | pass (non-mutating, baseline match) |
| `uv run pip-audit` | Yes | pass — no known vulnerabilities after v0.7.0 dependency updates |
| `uv run bandit -r src/` | Yes | pass (no medium/high) |
| `local-agent-harness check` | No | skip — tool not installed in this environment; equivalent drift coverage via `run_readiness_audit` (drift_findings: []) |

| Disabled gate | Justification |
|---|---|
| `local-agent-harness check` | Not installed on host; MCP readiness audit (report `readiness-audit:ykiWVWQjcuzzuQPMB9SlPgrb`, stage S3, no drift, no missing gates) provides the drift/gate coverage. Owner: grammy-jiang. Review due: next release. |

## Context And Cost Policy

| Field | Value |
|---|---|
| Context budget (tokens) | per AGENTS.md (70% compaction threshold) |
| Token spend (actual) | within session budget; no budget_warning emitted |
| Retry budget (limit) | 3 per tool call |
| Wall-clock budget (limit) | 30 min warning / 45 min hard stop |
| Wall-clock actual | release steps ~25 min (audit + gap closure earlier in session) |
| Compaction events | 0 |
| Budget hard stops | No |

## Telemetry

| Field | Value |
|---|---|
| Session trace location | server-side run records: `impl-check:ic:c68adab7e8ef45beadde63c66e629f0e` (audit), `recheck_gaps_report-20260612.json` (closure recheck); session plan `.agent/plan.md` |
| Trace completeness | complete |
| Redaction policy applied | per AGENTS.md; no red-class data observed |

## Evaluation Notes

| Field | Value |
|---|---|
| Known limitations | Vul4J calibration fixture-based (documented in evaluation-guide.md); HER ship gate needs LLM-enabled T2/T3 run; readiness eval tier T1/null-mode |
| Deviations from standard harness | clause investigation supplemented MCP FL with source greps (embedding retrieval unavailable) — recorded in plan.md decisions log |
| Waived controls | local-agent-harness check (see above) |

## Release Gates (ship skill T1–T4)

| Gate | Outcome |
|---|---|
| Incidents (P0/P1 open) | none — `.agent/incidents/` absent |
| T1 `make verify` on master @ 92e4179 | pass |
| T2 harness regression (`tests/harness/`) | pass (28 tests: manifest-regression, non-relaxation, semantic-mutation) |
| T3 drift check | pass — readiness audit `readiness-audit:ykiWVWQjcuzzuQPMB9SlPgrb`: drift_findings [], missing_gates [], stage S3, score 22 (no per-axis regression vs `readiness-audit:4kdVDmkGUutWTI_vMet5uD24`) |
| T4 calibration | fail-closed residual documented (evaluation-guide.md); not required for this stage per fixture-calibration precedent (v0.6.x releases) |

## Human Approval (HC3)

| Field | Value |
|---|---|
| Approval for tag + publish | Granted by Grammy Jiang in-session, 2026-06-12: "commit and merge to the main/master branch; then make a release … publish to github release and PyPI" |
| Proposed tag | v0.7.0 |
| Publish targets | GitHub Release (publish.yml) + PyPI via `PYPI_API_TOKEN` |

## Invariants (must hold)

- Positive verdict requires `Trace completeness: complete` — satisfied.
- Waived controls have justification, owner, review date — satisfied.
- Comparability fields filled — satisfied.
