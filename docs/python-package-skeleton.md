# Phase 0 Python Package Skeleton

Phase 0 establishes the package surfaces that later implementation phases use.
This repository already contains Phases 1-8, so the Phase 0 pass is additive:
existing indexing, storage, MCP, SARIF, plugin, and QA modules remain intact.

Current Phase 0 baseline:

- Python floor: 3.12.
- Dependency manager: `uv` with `uv.lock` as supply-chain evidence.
- CLI framework: Typer + Rich.
- JSONL writers: `orjson`.
- Formatting/lint order: `isort`, `black`, then `ruff`.
- Architecture gate: `.importlinter` plus `uv run lint-imports`.

Implemented skeleton surfaces:

- `llm_sca_tooling.config`: typed defaults, JSON/TOML loading, environment
  overrides, and redacted config output.
- `llm_sca_tooling.errors`: package-level structured errors.
- `llm_sca_tooling.telemetry`: logger setup and JSONL trace writer.
- `llm_sca_tooling.operations`: file-backed run-record writer and budget
  monitor.
- `llm_sca_tooling.governance`: permission profiles and policy evaluator.
- `llm_sca_tooling.harness`: Harness Condition Sheet writer.
- `llm_sca_tooling.cli.main`: Typer/Rich `llm-sca-tooling` command entrypoint.
- `llm_sca_tooling.plugins.registry.NoOpPlugin`: no-op plugin for skeleton
  registry tests.

The historical `evidence-sca` CLI remains available for existing graph and MCP
commands.

Useful commands:

```bash
uv sync --extra dev
llm-sca-tooling --version
llm-sca-tooling version
llm-sca-tooling config show
llm-sca-tooling config validate
llm-sca-tooling harness status
llm-sca-tooling run create demo
make verify
make verify-baseline
```
