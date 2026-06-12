# Session Plan: Implementation Completeness Check + Gap Closure

session_id: impl-completeness-20260612T150400+1000
started: 2026-06-12T15:04:00+10:00
mode: scoped-execute (was read-only for audit phase)
redaction_status: no_red_class_data_observed
branch: agent/close-impl-gaps

## Scope

Phase 1 (done): audit against architecture + implementation-plan docs.
Phase 2 (current): close audit gaps via fix skill `test-first-repair`:

1. **Gap 1 — monitor/budget run-event persistence** (architecture.md:326):
   - `src/llm_sca_tooling/workflows/bug_resolve/models.py` — add
     `BugResolveReport.monitor_events` field.
   - `src/llm_sca_tooling/workflows/bug_resolve/report.py` — populate it.
   - `src/llm_sca_tooling/mcp_server/tools.py` — `run_issue_resolution`
     handler: create run row, persist monitor events via
     `operations.append_run_event`, close run; honor already-advertised
     `config`/`run_id` args + simulate test-injection flags.
   - Tests: `tests/mcp_server/test_monitor_event_persistence.py` (new),
     `tests/workflows/bug_resolve/` additions.
2. **Gap 2 — hindsight relabeller interface + LLM boundary** (phase-17 §9):
   - `src/llm_sca_tooling/memory/relabelling/interface.py` (new — spec file
     missing), `llm_relabeller.py` (new), `__init__.py` exports.
   - Tests: `tests/memory/test_llm_relabeller.py` (new).
3. **Gap 3 — Vul4J live-calibration residual**: document in
   `docs/evaluation-guide.md`.

Out of scope: language-backend toolchains (ts-morph/libclang/JDT), live
benchmark execution, network-dependent calibration runs.

## Workflow

`implementation-check` (audit skill) via llm-sca-tooling MCP server session tools:

1. `register_repo` — done: `repo:670d359a49c6d7f1129bf84e`
2. `graph_build` — task `task:wocsPX1iHtJSFF-hYmZAk86jseohB8HR3UsKHnvM-SI`, polling
3. `run_implementation_check` — spec = architecture + implementation plan docs
4. Clause investigation — `get_relevant_files` per violated/unknown clause
5. `run_readiness_audit`
6. Synthesis — `.agent/artifacts/compliance_report.md`

## Commands

- MCP tools only for evidence gathering (audit skill mandate)
- Artifacts → `.agent/artifacts/`

## Expected outputs

- `.agent/artifacts/impl_check_report-20260612.json`
- `.agent/artifacts/clause_investigation-20260612.json`
- `.agent/artifacts/readiness_report-20260612.json`
- `.agent/artifacts/compliance_report-20260612.md`

## Risks

- Spec docs large (160K + 93K) — may need chunked spec submission
- Prior baseline: 2026-05-19 Phase C re-audit returned 19 unknowns; compare against it
- No LLM key wired into MCP server — expect heuristic/null-mode evidence grades
- `docs/completeness-report.md` is committed baseline — do not overwrite

## Decisions log

- 2026-06-12T15:04: Use session MCP connection (mcp__llm-sca-tooling__*) —
  satisfies audit-skill MCP mandate; no manual JSON-RPC needed.
- 2026-06-12T15:04: Prior session plan (Phase C re-audit 2026-05-19) archived by
  overwrite per AGENTS.md session-memory reset rule; baseline facts retained here.
- 2026-06-12T15:10: Spec (259K chars) passed via JSON-RPC helper script
  (`.agent/artifacts/run_impl_check_20260612.py`) so doc text never transits
  agent context; task-mode run polled to completion.
- 2026-06-12T15:20: `get_relevant_files` doc-bias (embedding unavailable) made
  pure-MCP clause grounding infeasible for source-level claims; recorded 6 MCP
  FL queries, then supplemented with targeted source greps cited file:line in
  `clause_investigation-20260612.json`. Deviation from audit-skill MCP-only
  lookup rule noted explicitly here and in the compliance report.

## Results

- `run_implementation_check`: partially_compliant — 945 satisfied / 0 violated /
  541 unknown (all `calibration_absent` + `no_hard_evidence`; no-LLM run).
- `run_readiness_audit`: stage S3, score 22, no drift findings, no missing gates.
- Clause sampling: 8/12 satisfied, 3/12 mechanism-complete-but-uncalibrated,
  0/12 missing. Details: `.agent/artifacts/clause_investigation-20260612.json`.
- Synthesis: `.agent/artifacts/compliance_report-20260612.md`.

## Verification

- `make verify-fast`: exit 0 (format, lint-imports, mypy strict — 375 files clean).
- `make verify-tests`: exit 0 (unit + harness suites; 28 harness tests passed,
  manifest-regression + non-relaxation + semantic-mutation all green).
- No source changes this session; writes confined to `.agent/` (plan + artifacts).
- Server-side run record: `impl-check:ic:c68adab7e8ef45beadde63c66e629f0e`;
  harness condition `hcs:impl-check:ic:c68adab7e8ef45beadde63c66e629f0e`.

## Remaining risk / uncertainty

- 541 unknown clauses ungrounded without LLM-in-loop re-run; sampled 12, others
  unexamined individually.
- Budget-notification → run-event persistence unverified (confidence 0.6).
- `manifest_regression_verdict: not_run` in impl-check report (covered separately
  by green `tests/harness/test_manifest_regression.py` in verify-tests).
