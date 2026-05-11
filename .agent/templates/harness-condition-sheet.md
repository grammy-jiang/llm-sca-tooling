# Harness Condition Sheet

> Copy this template into `.agent/eval/hcs-<run_id>.md` before each
> evaluation or release run. Fill in every field. A run claiming a positive
> verdict cannot have `Trace completeness: missing`.
>
> Two runs are only comparable when their HCS fields match on:
> runtime name/version, model backend/version, AGENTS.md revision,
> and permission profile.

---

## Identification

| Field | Value |
|---|---|
| Run ID | `<run_id>` |
| Report date | `<ISO-8601 date>` |
| Phase / milestone | `<e.g. H0 init, Phase 1 eval, release v0.1.0>` |
| Prepared by | `<human name or agent>` |

---

## Runtime And Model

| Field | Value |
|---|---|
| Runtime name | `<claude-code \| codex-cli \| copilot-cli>` |
| Runtime version | `<version string>` |
| Model backend | `<e.g. claude-sonnet-4-6>` |
| Model version / API version | `<version string>` |
| MCP server name | `<n/a or name>` |
| MCP server version | `<n/a or version>` |

---

## Manifest State

| Field | Value |
|---|---|
| AGENTS.md revision (git SHA) | `<sha>` |
| CLAUDE.md revision | `<sha or n/a>` |
| copilot-instructions.md revision | `<sha or n/a>` |
| .codex/INSTRUCTIONS.md revision | `<sha or n/a>` |
| SKILL.md template(s) active | `<list or n/a>` |

---

## Exposed Tools

| Field | Value |
|---|---|
| Tool set hash | `<hash of active MCP tools and versions>` |
| Tools active for this run | `<list>` |
| Tools disabled / unavailable | `<list or none>` |

---

## Permission Mode

| Field | Value |
|---|---|
| Permission profile | `<read-only \| plan \| scoped-edit \| scoped-execute \| review-commit>` |
| Path allowlist | `<summary or reference to AGENTS.md § Scope Boundary>` |
| Network policy | `<deny-by-default \| exceptions listed in AGENTS.md>` |
| Sandbox / devcontainer | `<devcontainer.json sha or "host — no sandbox">` |

---

## Verification Gates

| Gate | Enabled? | Outcome |
|---|---|---|
| `make verify` | Yes / No | pass / fail / skip |
| `uv run isort --check .` | Yes / No | pass / fail / skip |
| `uv run black --check .` | Yes / No | pass / fail / skip |
| `uv run ruff check .` | Yes / No | pass / fail / skip |
| `uv run lint-imports` | Yes / No | pass / fail / skip |
| `uv run mypy src/` | Yes / No | pass / fail / skip |
| `uv run pytest tests/unit/ -x` | Yes / No | pass / fail / skip |
| `uv run detect-secrets scan` | Yes / No | pass / fail / skip |
| `uv run pip-audit` | Yes / No | pass / fail / skip |
| `uv run bandit -r src/` | Yes / No | pass / fail / skip |
| `local-agent-harness check` | Yes / No | pass / fail / skip |

Any disabled gate requires a justification:

| Disabled gate | Justification |
|---|---|
| `<gate name>` | `<reason; owner; review-due date>` |

---

## Context And Cost Policy

| Field | Value |
|---|---|
| Context budget (tokens) | `<limit or "per AGENTS.md">` |
| Token spend (actual) | `<tokens used>` |
| Retry budget (limit) | `3 per tool call` |
| Wall-clock budget (limit) | `30 min warning / 45 min hard stop` |
| Wall-clock actual | `<HH:MM>` |
| Compaction events | `<count>` |
| Budget hard stops | `Yes / No` |

---

## Telemetry

| Field | Value |
|---|---|
| Session trace location | `<path or URL to JSONL trace file>` |
| Trace completeness | `complete \| incomplete \| missing` |
| Redaction policy applied | `<policy name or "per AGENTS.md">` |

---

## Evaluation Notes

| Field | Value |
|---|---|
| Known limitations | `<free text>` |
| Deviations from standard harness | `<list or none>` |
| Waived controls | `<list with reviewed justification, owner, expiry; or none>` |

---

## Invariants (must hold)

- A run claiming a positive verdict cannot have `Trace completeness: missing`.
- Every waived control must have a reviewed justification with owner and expiry date.
- Two runs are only comparable when runtime, model, manifest revision, and permission
  profile match on their respective HCS.
