# Repository Overview

_TODO: add a brief description of what this repository does._

## Tech Stack

Not yet determined — update this section when source code is added.

## Project Layout

```
.
├── .agent/
├── .claude/
├── .devcontainer/
├── AGENTS.md
├── CLAUDE.md
├── .gitignore
└── .pre-commit-config.yaml
```

## Build & Validation Commands

<!-- Project setup, build, test, and lint commands are in AGENTS.md
     (§Setup, §Testing, §Lint and Format) — loaded natively by Copilot
     CLI, Copilot Cloud Agent, Claude Code, and Codex CLI.
     VS Code Chat and Code Review users: see AGENTS.md directly. -->

```bash
# Agent harness
local-agent-harness check --repo .
local-agent-harness validate --repo .

# Pre-commit
pre-commit install       # first time only
pre-commit run --all-files
```

## Copilot-specific guidance

### Which Copilot product reads which files

| Product | Files loaded |
|---|---|
| **Copilot CLI** (terminal agent) | `AGENTS.md`, this file, `CLAUDE.md`, `.github/instructions/**/*.instructions.md` |
| **VS Code Copilot Chat** | This file, `.github/instructions/**/*.instructions.md` |
| **Copilot Cloud Agent** | `AGENTS.md`, this file |
| **Copilot Code Review** | This file |

> **VS Code Chat and Code Review** do not load `AGENTS.md` automatically.
> Review `AGENTS.md` for hard constraints (HC1–HC6), scope boundary,
> stop conditions, and PR checklist before using Copilot in this repo.

<!-- Add Copilot-only supplements below as the project grows
     (e.g., code review focus areas, path-specific notes via
     .github/instructions/*.instructions.md with applyTo: frontmatter). -->

## Notes

- `.agent/eval/` is gitignored; readiness reports are local only.
