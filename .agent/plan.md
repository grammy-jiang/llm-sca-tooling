# Session Plan: Audit Implementation Completeness And Release

session_id: audit-release-20260518T000137+1000
started: 2026-05-18T00:01:37+10:00
mode: scoped-execute
redaction_status: no_red_class_data_observed

## Scope

- Audit implementation completeness against the design and implementation-plan docs.
- Use the `audit` skill MCP workflow for implementation check, gap investigation, readiness, and patch review.
- If confirmed gaps are found, fix them in allowed paths only.
- If gates pass, commit the fix, prepare a package release, build the package, and upgrade the local `pipx` install.
- Write scope: `src/`, `tests/`, `schemas/`, `docs/`, `.agent/`, `.agents/skills/`, `AGENTS.md`, `CLAUDE.md`, `pyproject.toml`, `tox.ini`, `Makefile`, `.pre-commit-config.yaml`, `.github/workflows/`.
- Treat pre-existing `uv.lock` changes as user-owned unless a release command makes them relevant.

## Commands

- MCP server: `uv run llm-sca-tooling mcp serve --transport stdio`
- Audit tools: `register_repo`, `graph_build`, `run_implementation_check`, `get_relevant_files`, `run_readiness_audit`, `run_issue_resolution`, `run_patch_review`, `classify_patch_risk`, `run_static_analysis`
- Verification: `make verify`
- Release gates: `uv run pytest tests/harness/ -x`, MCP readiness and drift classification, `uv build --wheel`
- Install: `pipx upgrade` or equivalent local package setup command after build

## Steps

- [x] Read `AGENTS.md`, `audit` skill, and `ship` skill.
- [x] Collect design and implementation-plan doc text as the audit spec.
- [x] Run MCP implementation-check workflow and save artifacts.
- [x] Investigate violated or unknown clauses through MCP file-relevance tools.
- [x] Fix confirmed gaps (Findings 3, 4, 5 from prior docs audit).
- [x] Run regression tests for each fix (TDD).
- [x] Run `make verify` and record results.
- [ ] Commit verified changes (in progress).
- [ ] Run release gates, build the package, and upgrade local `pipx` install.
- [ ] Record final release/install outcome.

## Decisions Log

- 2026-05-18T00:01:37+10:00: User requested audit, fixes, commit, release, package build, and local `pipx` upgrade/setup. Use `audit` first, then `ship` release workflow after gates pass.
- 2026-05-18T00:01:37+10:00: `uv.lock` was dirty before this session; avoid reverting or overwriting it unless explicitly required by release workflow.
- 2026-05-18T08:50+10:00: User chose deep audit spec (architecture + plan, 250KB) and patch bump v0.4.4 if gaps fixed.
- 2026-05-18T08:55+10:00: Prior compliance report (May 17) verdict was `partially_compliant` with 0 violated and 6 unknown clauses — all extraction artifacts, no real gaps. Pivoted to verifying the 5 docs-audit findings on disk; readiness persistence tests pass (no fix needed), `.codex` overlay drift already fixed, Findings 3-5 remain open.
- 2026-05-18T09:10+10:00: User chose full fix for Finding 5 (column + persist HCS row) plus Findings 3-4 enhancements.
- 2026-05-18T09:30+10:00: Implemented all three fixes TDD: failing test → implementation → 126 tests pass. `make verify` exits 0 on all phases (format/lint/types/tests/security); dirty-check pinged `uv.lock` for the 0.4.2 → 0.4.4 sync, expected to clear once the commit lands.

## Verification

- 13 indexing scanner tests (Finding 3): PASSED
- 5 markdown backend tests (Finding 4): PASSED
- impl-check harness_condition_id linkage test (Finding 5): PASSED
- Broader regression sweep (`tests/indexing tests/impl_check tests/mcp_server`): 126 passed
- `make verify`: format/lint/types/tests/security all pass; dirty-check pending commit of `uv.lock` lock-sync.
