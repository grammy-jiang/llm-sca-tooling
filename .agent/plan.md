# Session Plan: Fix Implementation Audit Findings

session_id: fix-audit-findings-20260517T2214+1000
started: 2026-05-17T22:14:00+10:00
mode: scoped-execute
redaction_status: no_red_class_data_observed

## Scope

- Fix the implementation completeness audit findings from the previous run.
- Write scope: `src/`, `tests/`, `Makefile`, and this `.agent/plan.md`.
- Leave existing unrelated `uv.lock` changes untouched.
- Do not edit `.llm-sca/` or other out-of-scope files.

## Target Fixes

1. Implementation-check clause extraction should handle design and roadmap bullets that do not contain backtick code symbols.
2. `run_readiness_audit` should persist a readiness report that the readiness resource can read.
3. MCP server capabilities should advertise resource `listChanged` consistently with emitted notifications.
4. Bandit static-analysis adapter should avoid scanning the whole repository when a Python source root exists.
5. `make verify` should not fail because `detect-secrets` scans `.secrets.baseline` itself.

## Commands

- Targeted tests before and after fixes:
  - `uv run pytest tests/impl_check/test_phase14_impl_check.py -x`
  - `uv run pytest tests/mcp_server/test_phase4_mcp.py -x`
  - `uv run pytest tests/sarif/test_phase6_sarif.py -x`
  - `uv run pytest tests/harness/test_non_relaxation.py -x`
- Final gate: `make verify`

## Steps

- [x] Read `AGENTS.md` and `fix` skill.
- [x] Inspect existing implementations and tests.
- [x] Add failing coverage for each defect.
- [x] Apply source and Makefile fixes.
- [x] Run targeted tests.
- [x] Run `make verify`.
- [x] Record verification outcome.

## Decisions Log

- 2026-05-17T22:14:00+10:00: Treat the request as test-first repair for audit findings, with narrow source/test/Makefile scope.
- 2026-05-17T22:14:00+10:00: Previous `make verify` baseline failed in `detect-secrets` after format, imports, mypy, unit tests, and harness tests passed.
- 2026-05-17T22:21:16+10:00: Added failing tests for design-bullet extraction, readiness resource persistence, resource listChanged capability metadata, Bandit source-root scoping, and detect-secrets baseline exclusion.
- 2026-05-17T22:23:34+10:00: Applied fixes in `clause_extractor.py`, MCP capability/persistence paths, Bandit adapter, and `Makefile`.
- 2026-05-17T22:34:40+10:00: Full security checks passed through `detect-secrets`, `pip-audit`, and `bandit`; final dirty-check failed only because `uv.lock` was already modified before this fix session.

## Verification

- Targeted regression tests:
  - `uv run pytest tests/impl_check/test_phase14_impl_check.py::test_clause_extraction_captures_design_bullets_without_symbols tests/mcp_server/test_phase4_mcp.py::test_server_capabilities_resources_tools_and_prompts tests/mcp_server/test_phase4_mcp.py::test_run_readiness_audit_persists_readiness_resource tests/sarif/test_phase6_sarif.py::test_bandit_adapter_scans_src_root_when_present tests/harness/test_non_relaxation.py::test_makefile_detect_secrets_does_not_scan_baseline_file -q` passed, 5 tests.
  - `uv run pytest tests/impl_check/test_phase14_impl_check.py tests/mcp_server/test_phase4_mcp.py tests/sarif/test_phase6_sarif.py tests/harness/test_non_relaxation.py -q` passed, 62 tests.
- `make verify-fast` passed: format, import contracts, and mypy.
- `make verify` passed format, import contracts, mypy, unit tests, harness tests, `detect-secrets`, `pip-audit`, and `bandit`.
- `make verify` failed at `verify-dirty` because `uv.lock` is modified. `uv.lock` was dirty before this fix session and was intentionally not reverted.
- Local docs extraction smoke: current design and implementation-plan docs now extract 1524 clauses, avoiding the previous one-synthetic-unknown failure mode.
