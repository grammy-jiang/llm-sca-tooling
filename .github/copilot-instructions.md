# Repository Overview

_TODO: add a brief description of what this repository does._

## Tech Stack

Not yet determined — update this section when source code is added.

## Project Layout

```
.
├── .agent/
├── .claude/
├── .codex/
├── .devcontainer/
├── AGENTS.md
├── CLAUDE.md
├── .gitignore
└── .pre-commit-config.yaml
```

## Build & Validation Commands

<!-- Project setup, build, test, and lint commands are in AGENTS.md
     (§Setup, §Testing, §Lint and Format) — read natively by all agent
     runtimes (Claude Code, Codex CLI, Copilot Cloud Agent). -->

```bash
# Agent harness
local-agent-harness check --repo .
local-agent-harness validate --repo .

# Pre-commit
pre-commit install       # first time only
pre-commit run --all-files
```

## Copilot-specific guidance

<!-- Add Copilot-only supplements here as the project grows
     (e.g., code review focus areas, chat response preferences).
     Behavioral constraints, scope boundaries, stop conditions,
     and PR checklist live in AGENTS.md. -->

## Notes

- `.agent/eval/` is gitignored; readiness reports are local only.
