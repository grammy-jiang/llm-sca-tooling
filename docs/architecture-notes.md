# Architecture Notes

This document is a pointer to the architecture and design documents for
the LLM-SCA tooling project.

## Source Documents

- `llm-sca-tooling-architecture.md` — full architecture specification
- `llm-sca-tooling-tech-stack.md` — technology stack and rationale
- `llm-sca-tooling-implementation-plan.md` — phase-by-phase implementation plan

These documents live in the research vault and are not committed to this
repository. Reference them by their stable titles above when filing issues
or ADRs.

## Key Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Package manager | `uv` | Lockfile-based, fast, HC supply-chain compatible |
| Config | Pydantic v2 + pydantic-settings | Type-safe, env-var overlay, redaction support |
| Serialisation | `orjson` | Primary JSON I/O; no stdlib `json` in production code |
| Async runtime | `asyncio` + `anyio[trio]` | Standard library async; anyio for test compatibility |
| CLI framework | Typer + Rich | Type-hint-driven; Rich output isolated to `cli` layer |
| MCP server | FastMCP 2.x | Placeholder; tools/resources added in Phase 4 |

## Module Boundaries

Rich is restricted to `llm_sca_tooling.cli` — enforced by `import-linter`.
See `pyproject.toml` `[tool.importlinter]` for the contract definition.

## Paper Anchors (Phase 0)

- `survey-yang-2025`
- `survey-issue-resolution-2026`
- `agentless`
