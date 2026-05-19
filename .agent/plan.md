# Session Plan: Phase C Re-Audit And Follow-Ups

session_id: phase-c-reaudit-20260519T111547+1000
started: 2026-05-19T11:15:47+10:00
mode: scoped-execute
redaction_status: no_red_class_data_observed

## Scope

- Follow `.agent/docs/plan-07-next-session-re-audit-and-followups.md` and the Phase C follow-up.
- Fix the audit-tooling gaps that kept Phase C open:
  - default discoverability for symbol-level MCP query tools (`find_callers`, `find_callees`, `get_graph_slice`);
  - exact-file retrieval for docs/schema/template paths such as `.agent/templates/*.md` and `*.schema.json`.
- Preserve the Phase C documentation already written.
- Write scope: `.agent/`, `src/llm_sca_tooling/fl/`, `src/llm_sca_tooling/mcp_server/`, `tests/fl/`, and `tests/mcp_server/`.

## Commands And Tools

- MCP tools: `register_repo`, `graph_build`, `task_status`, `task_result`, `run_implementation_check`, `get_relevant_files`, `run_readiness_audit`.
- Pre-flight: `tool_search` for `task_status`, `get_relevant_files`, and `run_implementation_check` schemas.
- Repo inspection: `git status`, `git log`, `sed`, `rg`, `ls`.
- Verification: targeted pytest for new regressions, then `make verify` if feasible.

## Steps

- [x] Read `AGENTS.md`, the audit skill, and plan-07.
- [x] Confirm local `master` is at the expected PR #3 merge.
- [x] Confirm MCP pre-flight: `task_status` has `task_id`; `get_relevant_files` has `include_context_bundle`.
- [x] Register repo and build graph through MCP, polling with `task_status(task_id=...)`.
- [x] Run MCP implementation check from the architecture and implementation-plan docs.
- [x] Investigate actionable unknowns with `get_relevant_files(include_context_bundle=False)`.
- [x] Run MCP readiness audit.
- [x] Write date-stamped audit artifacts and compliance report.
- [x] Compare against the baseline report and evaluate Phase C acceptance criteria.
- [x] Update plan-06 §6 and Appendix B.7 with the result.
- [x] Run the appropriate verification gate and record results.
- [x] Write failing regression tests for MCP query-tool visibility and non-Python file mentions.
- [x] Fix MCP query-tool tiers and file mention extraction.
- [x] Fix `RunRecordWriter` thread-offload hang exposed by `make verify`.
- [x] Run targeted tests and verification.

## Decisions Log

- 2026-05-19T11:15:47+10:00: User asked to follow plan-07 and keep working. Treat Phase C re-audit as the main task.
- 2026-05-19T11:15:47+10:00: Pre-flight via tool discovery shows both repaired schemas are visible in this session, so proceed without reinstalling the MCP server.
- 2026-05-19T11:18:11+10:00: Phase C verifies M1/M2/M3 mechanics, but criterion C remains open because the focused re-audit still returned 19 unknowns and MCP relevance stayed doc-biased with embedding retrieval unavailable.
- 2026-05-19T11:30:00+10:00: Continue with `fix` skill test-first repair. Root causes identified so far: query tools are tier 3 while default `tools/list` exposes tiers 1-2; issue file extraction ignores `.md`/`.json` paths, which suppresses exact-file retrieval for templates and schemas.
- 2026-05-19T12:06:47+10:00: Full `make verify` isolated a pre-existing CLI hang in `RunRecordWriter.create_run`; `asyncio.to_thread` blocked in this sandbox. Replaced thread offload with direct local file writes.
- 2026-05-19T12:37:00+10:00: `detect-secrets scan` can remain parallel in normal environments. The Makefile now tries the native parallel CLI path first and falls back to serial scanning only when this sandbox rejects multiprocessing.

## Verification

- `make verify-docs`: failed before running checks because uv tried to write under read-only `/home/grammy-jiang/.cache/uv`.
- `UV_CACHE_DIR=/tmp/uv-cache make verify-docs`: passed on 2026-05-19; format check reported 506 files unchanged.
- New focused regressions:
  - `UV_CACHE_DIR=/tmp/uv-cache timeout 120 uv run pytest tests/fl/test_phase9_fl.py::test_issue_normalizer_extracts_docs_schema_and_template_paths tests/mcp_server/test_task_tool_schemas.py::test_symbol_query_tools_are_default_discoverable -x`: passed.
  - `UV_CACHE_DIR=/tmp/uv-cache timeout 60 uv run pytest tests/unit/test_cli.py::test_run_create_exits_zero tests/unit/test_cli.py::test_run_create_reports_writer_error -x`: passed.
- `BLACK_NUM_WORKERS=1 UV_CACHE_DIR=/tmp/uv-cache make verify-fast`: passed.
- `BLACK_NUM_WORKERS=1 UV_CACHE_DIR=/tmp/uv-cache timeout 3000 make verify`: format/imports/types passed; tests passed (142 unit + 28 harness); detect-secrets passed via sandbox fallback; stopped at `pip-audit` because network/DNS to `pypi.org` is unavailable in this sandbox.
- `BLACK_NUM_WORKERS=1 UV_CACHE_DIR=/tmp/uv-cache timeout 300 make _sast`: passed; Bandit reported no medium/high issues.
- `BLACK_NUM_WORKERS=1 UV_CACHE_DIR=/tmp/uv-cache timeout 120 make verify-dirty`: passed; `uv.lock` and `.secrets.baseline` unchanged.
