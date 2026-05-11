# Session Plan - phase-18-release-gates

> Ephemeral but auditable. Updated during the session.

## Inputs
- Task statement: Check whether Phase 18 is implemented; if not, implement it, otherwise implement Phase 19.
- Linked issue / PR: n/a
- Maturity stage at session start: S2 inferred from existing harness, eval, workflow, and memory artefacts.

## Non-goals
- Do not implement Phase 19 distribution, watcher, packaging, HTTP transport, or docs work because Phase 18 is not implemented.
- Do not use live external benchmark services or network egress.
- Do not execute destructive commands, publish packages, tag releases, or modify git internals.

## Allowed scope
- Files: `src/llm_sca_tooling/evaluation/`, `src/llm_sca_tooling/release/`, `src/llm_sca_tooling/mcp_server/`, `src/llm_sca_tooling/cli/`, `src/llm_sca_tooling/workflows/bug_resolve/`, `tests/`, `.agent/plan.md`
- Commands: `git status`, `git diff`, `uv run pytest tests/ -x`, `uv run pytest tests/unit/ -x`, `uv run pytest tests/harness/ -x`, `make verify`, `local-agent-harness check --repo .`
- Network: denied

## Proposed steps
1. Confirm Phase 18 implementation status from docs, source, and tests.
2. Add Phase 18 typed release/evaluation models and deterministic null-mode services.
3. Add T3/T4 eval runners and replace Phase 10 T3/T4 stubs.
4. Add release gate JSON report writer and CLI command.
5. Add full operational-review/readiness-audit launchers and prompt text.
6. Add Phase 18 tests covering calibration, gates, runners, release command, tools, and prompts.
7. Run allowed verification commands and record outcomes.

## DryRUN predictions
- Files to touch: new `src/llm_sca_tooling/release/*`, new `src/llm_sca_tooling/evaluation/t3_runner.py`, `t4_runner.py`, updates to `t2_runner.py`, `__init__.py`, MCP tools/prompts, CLI main, and tests.
- Tests to run: `uv run pytest tests/ -x`, then `make verify`.
- Expected diff size: large because Phase 18 introduces a new release-gate surface.
- Expected risk: medium; changes touch CLI and MCP registration but are additive and deterministic.

## Verification
- [x] Lint - `uv run ruff check .` passed; `make verify` format/lint/import contracts passed.
- [x] Tests - `uv run pytest tests/ -x` passed 491 tests; `make verify` unit and harness subsets passed.
- [x] Secrets scan - `make verify` ran `detect-secrets scan --baseline .secrets.baseline`.
- [x] SAST / deps (if S2+) - `make verify` ran `pip-audit` and `bandit`; no blocking findings.
- [x] Maintainability gate (if S2+) - import-linter architecture contract kept; no Rich leakage outside CLI.
- [x] Manifest regression (if manifests changed) - `make verify` harness tests passed; `local-agent-harness check --repo .` reported Stage S2 and no drift.

## Decisions log
- 2026-05-10 - Phase 18 selected - docs include Phase 18/19 plans, but source lacks Phase 18 release package, T3/T4 runners, and Phase 18 tests.
- 2026-05-10 - Deterministic local fixtures selected - external benchmark/network execution is out of scope and HC5-denied for agent execution.
- 2026-05-10 - Phase 13 compatibility fix admitted - full verification exposed a blast-radius stub regression where partial Phase 15 output lost the changed symbol itself.
- 2026-05-10 - Verification complete - `make verify` and `local-agent-harness check --repo .` both exited 0.
