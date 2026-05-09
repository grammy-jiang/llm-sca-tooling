# AGENTS.md

> Agent instructions for this repository.
> This is the **shared spine** read natively by all agent runtimes
> (OpenAI Codex, Claude Code via `@AGENTS.md`, GitHub Copilot).
> Agent-specific overlays live in `.codex/INSTRUCTIONS.md`,
> `CLAUDE.md`, and `.github/copilot-instructions.md`.
> See also: `.agent/plan.md` (session plan).

## Project Overview

`evidence-sca` (`llm-sca-tooling`) is a Python package for
LLM-assisted static code analysis. It builds typed repository evidence,
stores graph/SARIF facts, exposes a local MCP facade, and provides
repository QA tools.

**Tech stack:** Python 3.12–3.14 · uv · Pydantic v2 · Typer/Rich ·
FastMCP/FastAPI · SQLModel · SQLite/PostgreSQL · pytest · GitHub Actions ·
local agent-harness governance layer.

**Layout:**
```
.
├── src/llm_sca_tooling/   # package source
├── tests/                  # pytest suite
├── schemas/                # JSON/SARIF schemas
├── fixtures/               # test fixture repos
├── docs/                   # design docs and templates
├── .agent/                 # harness artefacts, plans, skills
├── .claude/                # Claude Code settings
├── .codex/                 # Codex CLI overlay
└── .github/                # Actions workflows + Copilot instructions
```

<!-- local-agent-harness:auto:begin -->
<!-- stack: Python -->
## Setup

```bash
pip install -e '.[dev]'  # or: uv sync
```

## Build

```bash
# see Makefile for available tasks
```

## Testing

```bash
pytest
pytest path/to/test_file.py::test_function_name
```

## Lint and Format

```bash
ruff check src tests
mypy src  # strict mode
ruff format src tests
```

## Code Style

- Line length: 88
- mypy --strict enforced on src/
- Target Python: py312–py314

<!-- local-agent-harness:auto:end -->

## Conventions

- Branch naming: `agent/<task-slug>`
- Commit style: Conventional Commits
- Keep functions small and single-purpose.
- Match the existing code style and patterns already in use.
- Prefer explicit error handling over silent failures.
- Run the test suite and linter after every change.
- Never push directly to `main`; always open a pull request.
- `.gitignore` has a managed section below the `# local-agent-harness` marker — do not hand-edit that section.

## Success Definition

A change is complete only when it has correct behaviour, maintainable
structure, policy compliance, and a traceable process. Feature acceptance
requires a Harness Condition Sheet, a session trace or explicit trace
limitation, and a passing verify path. A demo result without telemetry,
verification, and review evidence is not release evidence.

## Scope Boundary

| Action | Allowed scope |
|---|---|
| Read   | entire repo |
| Edit   | `src/`, `tests/`, `docs/`, `schemas/`, `fixtures/`, `.agent/`, `.codex/`, `.github/`, `AGENTS.md`, `CLAUDE.md`, `.importlinter`, `.pre-commit-config.yaml`, `.secrets.baseline`, `pyproject.toml`, `tox.ini`, `Makefile` |
| Create | within edit scope |
| Delete | requires human approval |
| Execute | see `.agent/policies/commands.allowlist` |

## Security and Hard Constraints

All hard constraints are enforced at every stage and may never be relaxed.

- **HC1** — No plaintext secrets in repository, prompts, logs, or commits.
- **HC2** — No writes outside the repository working tree.
- **HC3** — Destructive commands (`rm -rf`, `git push --force`, schema drops,
  package publishes) require explicit human approval.
- **HC4** — Migrations and irreversible operations may be authored but never
  executed by the agent.
- **HC5** — Network egress is denied by default; allowlist in `AGENTS.md`.
- **HC6** — Red-class data (secrets, PII, customer data) never enters prompts,
  tool arguments, or logs.

**Data classification:**

| Class | Examples | In prompts? | In logs? |
|---|---|---|---|
| Green | OSS source, public docs | yes | yes |
| Amber | Internal source, non-PII configs | yes (redact tokens) | redacted |
| Red | Secrets, PII, customer data, keys | **no** | **no** |

Use the `detect-secrets` pre-commit hook with `.secrets.baseline`; keep
Gitleaks as an additional harness compatibility scanner. Run the harness
validation gate before every PR.

## Quality Gate

Use the repo-local verify entrypoint:

```bash
make verify
```

The verify path follows the Phase H0 sequence: import sorting, formatting,
Ruff, import-linter, mypy, unit tests, secrets scan, dependency audit, Bandit,
schema freshness, manifest regression tests, and `local-agent-harness validate`
when installed. `make verify-baseline` exists only for local diagnosis of the
older compile/test/schema baseline.

## Tool Categories And Permissions

| Category | Examples | Default rule |
|---|---|---|
| read | file read, symbol lookup, repo query | allowed |
| search | grep, glob, semantic search | allowed |
| edit | file edits, tests, schemas | scoped path required |
| execute | shell commands, tests, formatters, scanners | allowlisted command required |
| review | diff analysis, gate evaluation | allowed after edits |
| commit | git commit, PR, tag | explicit approval or passing review gate |

Permission profiles are `read-only`, `plan`, `scoped-edit`,
`scoped-execute`, and `review-commit`. Network egress is denied by default
unless a task-specific allow entry is documented and approved.

## Cost Policy

- Default retry budget: 3 attempts per failing command before changing
  strategy.
- Doom-loop stop: 5 similar calls with similar arguments.
- Default wall-clock budget for a single agent session: 1 hour unless the user
  explicitly asks for a longer run.
- Context compaction must preserve this file, `.agent/plan.md`, the current
  diff, and recent verification evidence.

## Verify-Before-Commit

Before commit or PR, run `make verify`. If a required tool or network access is
unavailable in the current environment, record the exact command, failure, and
residual risk. Do not waive failed gates silently.

## Memory Governance

Session notes, failures, and lessons are not durable policy by default.
Promote a lesson only after review, with source links, owner, review due date,
acceptance check, and rollback path.

## Lesson Promotion Policy

Promotion candidates must reference the originating run, event, test, incident,
or review. A promoted lesson may not override current hard evidence, HC1-HC6,
or the path/network policy.

## Harness Artefacts

- Harness overview: `docs/harness.md`
- Harness Condition Sheet template: `docs/harness-condition-sheet.md`
- Operational review template: `docs/operational-review-template.md`
- Incident record template: `docs/incident-record-template.md`
- Harness stage record: `.agent/harness-stage.json`
- Skill templates: `.agent/skills/*/SKILL.md`

## Stop Conditions

Applies to all agents:

- Doom-loop: if the same tool is called 5× with similar args, stop and ask.
- Out-of-scope write: abort + revert + report.

## PR Checklist

1. All tests pass; add tests for every new function and every bug fix.
2. Linter and formatter clean.
3. No new secrets or SAST findings.
4. PR description: change summary, risks, verification evidence; call out any dependency changes explicitly.
5. Keep PRs small and focused; split unrelated changes into separate PRs.
6. Append a `Decisions log` entry in `.agent/plan.md` for non-trivial choices.


## Success Definition

A change is complete only when it has correct behaviour, maintainable
structure, policy compliance, and a traceable process. Feature acceptance
requires a Harness Condition Sheet, a session trace or explicit trace
limitation, and a passing verify path. A demo result without telemetry,
verification, and review evidence is not release evidence.

## Scope Boundary

| Action | Allowed scope |
|---|---|
| Read   | entire repo |
| Edit   | `src/`, `tests/`, `docs/`, `schemas/`, `fixtures/`, `.agent/`, `.codex/`, `.github/`, `AGENTS.md`, `CLAUDE.md`, `.importlinter`, `.pre-commit-config.yaml`, `.secrets.baseline`, `pyproject.toml`, `tox.ini`, `Makefile` |
| Create | within edit scope |
| Delete | requires human approval |
| Execute | see `.agent/policies/commands.allowlist` |

## Security and Hard Constraints

All hard constraints are enforced at every stage and may never be relaxed.

- **HC1** — No plaintext secrets in repository, prompts, logs, or commits.
- **HC2** — No writes outside the repository working tree.
- **HC3** — Destructive commands (`rm -rf`, `git push --force`, schema drops,
  package publishes) require explicit human approval.
- **HC4** — Migrations and irreversible operations may be authored but never
  executed by the agent.
- **HC5** — Network egress is denied by default; allowlist in `AGENTS.md`.
- **HC6** — Red-class data (secrets, PII, customer data) never enters prompts,
  tool arguments, or logs.

**Data classification:**

| Class | Examples | In prompts? | In logs? |
|---|---|---|---|
| Green | OSS source, public docs | yes | yes |
| Amber | Internal source, non-PII configs | yes (redact tokens) | redacted |
| Red | Secrets, PII, customer data, keys | **no** | **no** |

Use the `detect-secrets` pre-commit hook with `.secrets.baseline`; keep
Gitleaks as an additional harness compatibility scanner. Run the harness
validation gate before every PR.

## Quality Gate

Use the repo-local verify entrypoint:

```bash
make verify
```

The verify path follows the Phase H0 sequence: import sorting, formatting,
Ruff, import-linter, mypy, unit tests, secrets scan, dependency audit, Bandit,
schema freshness, manifest regression tests, and `local-agent-harness validate`
when installed. `make verify-baseline` exists only for local diagnosis of the
older compile/test/schema baseline.

## Tool Categories And Permissions

| Category | Examples | Default rule |
|---|---|---|
| read | file read, symbol lookup, repo query | allowed |
| search | grep, glob, semantic search | allowed |
| edit | file edits, tests, schemas | scoped path required |
| execute | shell commands, tests, formatters, scanners | allowlisted command required |
| review | diff analysis, gate evaluation | allowed after edits |
| commit | git commit, PR, tag | explicit approval or passing review gate |

Permission profiles are `read-only`, `plan`, `scoped-edit`,
`scoped-execute`, and `review-commit`. Network egress is denied by default
unless a task-specific allow entry is documented and approved.

## Cost Policy

- Default retry budget: 3 attempts per failing command before changing
  strategy.
- Doom-loop stop: 5 similar calls with similar arguments.
- Default wall-clock budget for a single agent session: 1 hour unless the user
  explicitly asks for a longer run.
- Context compaction must preserve this file, `.agent/plan.md`, the current
  diff, and recent verification evidence.

## Verify-Before-Commit

Before commit or PR, run `make verify`. If a required tool or network access is
unavailable in the current environment, record the exact command, failure, and
residual risk. Do not waive failed gates silently.

## Memory Governance

Session notes, failures, and lessons are not durable policy by default.
Promote a lesson only after review, with source links, owner, review due date,
acceptance check, and rollback path.

## Lesson Promotion Policy

Promotion candidates must reference the originating run, event, test, incident,
or review. A promoted lesson may not override current hard evidence, HC1-HC6,
or the path/network policy.

## Harness Artefacts

- Harness overview: `docs/harness.md`
- Harness Condition Sheet template: `docs/harness-condition-sheet.md`
- Operational review template: `docs/operational-review-template.md`
- Incident record template: `docs/incident-record-template.md`
- Harness stage record: `.agent/harness-stage.json`
- Skill templates: `.agent/skills/*/SKILL.md`

## Stop Conditions

Applies to all agents:

- Doom-loop: if the same tool is called 5× with similar args, stop and ask.
- Out-of-scope write: abort + revert + report.

## PR Checklist

1. All tests pass; add tests for every new function and every bug fix.
2. Linter and formatter clean.
3. No new secrets or SAST findings.
4. PR description: change summary, risks, verification evidence; call out any dependency changes explicitly.
5. Keep PRs small and focused; split unrelated changes into separate PRs.
6. Append a `Decisions log` entry in `.agent/plan.md` for non-trivial choices.
