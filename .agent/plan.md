# Session Plan - implement-phase-h0-and-0

## Inputs
- Task statement: Sync the repository with the revised Phase H0, Phase 0, and
  tech-stack plans from `/home/grammy-jiang/Documents/Research/static-code-analysis/`.
- Linked issue / PR: n/a
- Maturity stage at session start: S2, based on `.agent/eval/readiness.md`.

## Non-goals
- Do not rewrite or downgrade existing Phase 1-8 product modules.
- Do not execute irreversible migrations or destructive commands.
- Do not introduce LLM calls, workflow orchestration, or Phase 9+ features.

## Allowed scope
- Baseline scope from `AGENTS.md`: `src/`, `tests/`, `docs/`, `.agent/plan.md`.
- Required H0/0 scope expansion: `AGENTS.md`, `CLAUDE.md`, `.codex/`, `.github/`, `.pre-commit-config.yaml`, `.agent/`, `.skills/`, `Makefile`, `pyproject.toml`, `tox.ini`, `fixtures/`.
- Commands: `rg`, `sed`, `git status`, `pytest`, `python -m compileall`, targeted CLI smoke commands, optional `make verify` if local tools are available.
- Network: denied.

## Proposed steps
1. Compare the external Phase H0/0 plans with current repo state and identify additive gaps.
2. Add missing H0 templates, docs, stage/readiness records, manifest regression tests, and verify entrypoint.
3. Add Phase 0 skeleton modules and CLI entrypoint in a way that preserves existing `evidence-sca` CLI behavior.
4. Add focused tests for the new skeleton contracts.
5. Run targeted and broad verification, then record results and decisions.

## DryRUN predictions
- Files to touch: H0 manifests/templates/docs/tests plus new Phase 0 skeleton modules under `src/llm_sca_tooling/`.
- Tests to run: targeted tests for new modules, existing full `pytest`, `python -m compileall src tests`.
- Expected diff size: large, because H0/0 are foundational and the repo already skipped them.
- Expected risk: medium. The main risk is changing package/CLI metadata or plugin/governance names in a way that breaks existing Phase 1-8 imports.

## Verification
- [x] Targeted Phase 0 tests - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_cli.py tests/unit/test_config.py tests/unit/test_telemetry.py tests/unit/test_operations.py tests/unit/test_harness_condition.py` passed with 13 tests.
- [x] Full tests - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` passed with 178 tests.
- [x] Baseline gate - `make verify-baseline` passed, including compile, full pytest, schema freshness, harness tests, and `local-agent-harness validate`.
- [x] Secrets scan - `make secrets-scan` passed using the detect-secrets baseline.
- [x] Dependency audit - `make dependency-audit` passed after approved network access; no known vulnerabilities found, local editable package skipped.
- [x] SAST high-severity gate - `make sast` passed with no high-severity Bandit findings; low/medium findings remain as warnings.
- [x] Harness drift - `local-agent-harness check --repo .` passed after retaining Gitleaks as a compatibility scanner.
- [x] Harness validate - `local-agent-harness validate --repo .` passed.
- [x] Strict Phase H0 gate attempted - `make verify` fails at repo-wide `isort --check` on pre-existing Phase 1-8 files.
- [x] Import architecture gate attempted - `uv run lint-imports` now runs and reports existing architecture violations involving `indexing -> plugins` and `indexing/storage -> sarif`.

## Decisions log
- 2026-05-09T07:32:17Z - Implement H0/0 additively - the repository already contains Phases 1-8, so existing product modules and CLIs should be preserved and new skeleton surfaces should be compatibility layers where possible.
- 2026-05-09T08:05:00Z - Disable Git commit signing only for test subprocesses - the sandbox inherits a global signing config but cannot write to `~/.gnupg`, and the tests only need unsigned temporary commits.
- 2026-05-09T09:20:18Z - Adopt the revised Python 3.12 + uv + hatchling package baseline and refresh `uv.lock`.
- 2026-05-09T09:20:18Z - Omit `pydantic-mypy` as a dependency because `uv lock` confirmed it is not a package in the registry; keep `plugins = ["pydantic.mypy"]` because the plugin ships with Pydantic.
- 2026-05-09T09:20:18Z - Make `make verify` a non-mutating strict Phase H0 gate and keep `make verify-baseline` for the passing legacy compile/test/schema baseline.
- 2026-05-09T10:15:00Z - Restrict Bandit's blocking gate to high severity so medium findings remain visible warnings, matching the revised H0 failure policy.
- 2026-05-09T10:15:00Z - Reverted accidental broad formatting changes from a miswired `make verify` target; kept only intended Phase H0/0 plan-sync edits.
- 2026-05-09T10:17:00Z - Keep detect-secrets as the revised H0 primary scanner and retain Gitleaks in pre-commit/CI to satisfy the current local-agent-harness drift rules.
