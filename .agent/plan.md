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

## Gap closure (phase 2)

- Branch `agent/close-impl-gaps`, 4 commits:
  1. `chore(deps)` — CVE remediation: idna 3.18, pyjwt 2.13.0, starlette 1.3.0,
     pip 26.1.2; pip-audit clean; ledger updated. (Pre-existing master breakage:
     verify was failing on pip-audit before this session's changes.)
  2. `fix(mcp-server)` — monitor/budget events persisted as run events
     (architecture.md:326). New tests: tests/mcp_server/test_monitor_event_persistence.py (4).
  3. `feat(memory)` — HindsightRelabellerInterface + LLMHindsightRelabeller +
     policy-guarded relabel_and_store (phase-17 §9). New tests:
     tests/memory/test_llm_relabeller.py (6).
  4. `docs(evaluation)` — Vul4J fixture-calibration residual documented.
- `make verify` exit 0 (all phases incl. detect-secrets, pip-audit, bandit,
  dirty-check).
- Closure recheck (`recheck_gaps_report-20260612.json`): 6/8 satisfied,
  0 violated, 2 unknown (behavioural clauses; fail-closed grading without LLM;
  both pinned by green deterministic tests).

## Release v0.7.0 (phase 3)

- PR #5 merged (92e4179); release commit 82dc28d; annotated tag v0.7.0 pushed.
- Gates: no incidents; T1 `make verify` pass (pre-bump and on release commit);
  T2 harness 28 tests pass; T3 readiness audit
  `readiness-audit:ykiWVWQjcuzzuQPMB9SlPgrb` — no drift, no regression (S3/22);
  HCS `.agent/eval/hcs-release-v0.7.0.md`; HC3 approval recorded (user,
  in-session).
- CI: publish 27398730363 ✓ (PyPI + GitHub Release), verify 27398721496 ✓,
  governance ✓. GitHub Release v0.7.0 carries wheel + sdist.
- Local: pipx upgraded 0.6.3 → 0.7.0; `config validate` exit 0; stdio
  handshake OK; global MCP config (`llm-sca-tooling mcp serve`) picks up
  0.7.0 on next session start.

## Tier A gap closure (phase 4)

branch: agent/tier-a-gaps. Scope (from feature-gaps-20260612.md):

- **A1** embedding retrieval: `fl/embedding_adapters/fastembed_adapter.py` (new,
  import-guarded, injectable encoder), factory in `embedding_adapters/__init__`,
  new `fl/embedding_retrieval.py` signal stream, wire into
  `fl/localisation.py` (adapter param + merge + signals_missing),
  `pyproject.toml` optional extra `embeddings = ["fastembed>=0.3"]`.
  Tests: `tests/fl/test_embedding_adapter.py` (new).
- **A2** stage 6b wiring: `run_implementation_check` gains optional
  `dynamic_verdicts` map; `report.py` uses injected record else dormant hook.
  Tests: `tests/impl_check/` addition exercising trace-derived verdict via
  `make_dynamic_verdict_from_trace`.
- **A3** `null_mode` arg honored in `run_issue_resolution` handler
  (`mcp_server/tools.py`). Test in
  `tests/mcp_server/test_monitor_event_persistence.py` or new file.
- **A4** CI Node 24: bump `actions/checkout@v4→v5`, `astral-sh/setup-uv@v3→v7`,
  `upload/download-artifact@v4→v5`, `softprops/action-gh-release@v2→v3` in
  publish/verify/governance workflows (governance-review files; user approved).
  Proof = CI runs on PR.

Out of scope: VectorCache wiring into embedding retrieval (follow-up), Tier B–D.

## Release v0.8.0 (phase 5)

- PR #6 merged (d0bac8d); release commit 1d1e874; tag v0.8.0 pushed.
- Gates: no incidents; readiness `readiness-audit:tSeslYw_KvnvqaEXKHg3sSxp`
  (S3/22, no drift/regression); `make verify` exit 0 on release commit;
  HCS `.agent/eval/hcs-release-v0.8.0.md`; HC3 approval in-session.
- CI: publish 27411031003 ✓, verify 27411030502 ✓ (both on Node 24 actions).
- Local: pipx 0.7.0 → 0.8.0; `pipx inject llm-sca-tooling fastembed` done;
  `get_default_embedding_adapter()` → FastembedEmbeddingAdapter available=True
  (BAAI/bge-small-en-v1.5; model downloads on first embed, then cached).
- Next agreed step: Tier B seams (B1 contract generator first), then
  VectorCache wiring.

## B1 — LLM contract generator (phase 6)

branch: agent/b1-contract-generator. Scope:

- `src/llm_sca_tooling/impl_check/contract_generator.py` — add
  `LLMContractGenerator` (injectable `complete()`, relabeller pattern):
  generates python predicate artifacts; `compile_check` via `ast.parse`;
  fail-closed fallback to null-equivalent natural_language_probe.
- `src/llm_sca_tooling/impl_check/report.py` — optional `contract_generator`
  param (default NullContractGenerator), mirrors `dynamic_verdicts` pattern.
- Tests: `tests/impl_check/test_llm_contract_generator.py` (new, fail-first).
- Spec rule enforced: "Generated predicates/tests must compile or lint before
  they can contribute hard evidence; otherwise they remain soft candidate
  artefacts" — failed compile → `compile_status="failed"` → static verdict
  stays unknown.

## Tier B completion (phase 7)

- PR #7 (B1 contract generator) merged: 1c0ad55.
- PR #8 (branch agent/tier-b-seams): B2 LLMSynthesisAdapter (qa),
  B3 LLMTraceSummarizer (traces), VectorCache wiring (fl). CI green.
- All boundaries share the pattern: injected complete(), HC5-clean,
  fail-closed, citations/events filtered to provided evidence, no trust
  upgrade. Defaults unchanged (null adapters).
- Verification: make verify exit 0; 9 new fail-first tests; 112 green.
- Remaining queue after merge: Tier C (language backends, protocol plugins),
  Tier D (LLM-enabled re-audit, live benchmarks), provider wiring for the
  four LLM boundaries (one shared completion-callable factory).

## Release v0.9.0 (phase 8)

- PR #8 merged (7422e33); release commit 3dd6aab; tag v0.9.0 pushed.
- Gates: no incidents; readiness `readiness-audit:xODJAFehbflOnEFTUW2aYNAC`
  (S3/22, no drift/regression); make verify exit 0 on release commit;
  HCS `.agent/eval/hcs-release-v0.9.0.md`; HC3 approval in-session.
- CI: publish + verify green; GitHub Release + PyPI live.
- Local: pipx 0.8.0 → 0.9.0; injected fastembed persisted through upgrade;
  all four LLM boundaries importable from installed package.
- Next agreed queue: provider wiring (shared completion-callable factory),
  then LLM-enabled re-audit, then Tier C/D.

## Provider wiring + re-audit prep (phase 9)

- PR #9 (agent/provider-wiring): llm/completion.py factory (anthropic SDK,
  optional extra `llm`), LLMGroundingAdapter (the actual unknown-mover —
  aggregator analysis showed unknowns are ungrounded prose; contract
  generator can't flip them), MCP `llm_mode` fail-soft wiring with
  llm_mode_active payload flag. CI green; make verify exit 0; 11 new tests.
- #2 (LLM re-audit) blocked on ANTHROPIC_API_KEY (absent in env).
  Runner ready: `.agent/artifacts/run_llm_reaudit.py` — compares against
  945/0/541 baseline. `uv sync --extra llm` + export key + run.
- Cost note: ~541 grounding calls; opus-4-8 default ≈ $5-10;
  LLM_SCA_MODEL=claude-haiku-4-5 for cheap first pass.

## Release v0.10.0 (phase 10)

- PR #9 (provider wiring) + PR #10 (README/LICENSE/metadata) merged; release
  commit c0cfd97; tag v0.10.0 pushed.
- Gates: no incidents; readiness `readiness-audit:XW6EQIIRw79inCVcemrO6Mhw`
  (S3/22, no drift/regression); make verify exit 0 on release commit;
  HCS `.agent/eval/hcs-release-v0.10.0.md`; HC3 approval ("Release").
- CI: publish + verify + governance all green (one stale-run-id watch false
  alarm, confirmed green via run-list conclusions).
- Local: pipx 0.9.0 → 0.10.0; embedding active; completion_available False
  (expected — no key; fail-soft default shipped).
- LLM re-audit still parked (no API key); runner staged.
- Next queue (user-picked order pending): llm_mode parity for synthesis /
  summarizer / patch-gen, java backend registration check, namespace
  cleanups, local-agent-harness waiver retirement.

## Queue items 1-4 (phase 11)

- PR #11 (agent/queue-items), 4 commits, CI green:
  1. llm_mode parity: synthesis/summarizer/CompletionPatchGenerator behind
     _resolve_llm_complete(); llm_mode_active in payloads.
  2. JavaBackend wired into IndexingService (both paths), behind
     LLM_SCA_JAVA_BACKEND_ENABLED gate; was never imported (root cause).
  3. graph/__init__ placeholder resolved; re-exports GraphQueryStore.
  4. AGENTS.md: readiness-audit codified as local-agent-harness equivalent
     (Quality Gate 7 + PR checklist 8); non-relaxation tests green.
- Item 5 parked (key/data): LLM re-audit runner staged, Vul4J/HER/toolchains.
- **Discovered, pre-existing, unfixed**: 9 failures in full pytest run on
  master (8 schema-file-vs-model regressions, 1 graph-store rollback test);
  verify gate covers only tests/unit + tests/harness so these never gated.
  Candidate next work: schema regeneration + rollback fix + consider adding
  full-suite CI job.

## Test-debt fix (phase 12)

- PR #12 (agent/fix-test-debt), 4 commits, CI green including the NEW
  full-suite step:
  1. schema exporter emits POSIX trailing newline (root cause of all 8
     schema regressions: exporter vs end-of-file-fixer fight).
  2. stale batch-edge test rewritten to documented skip contract (26e5140).
  3. verify.yml runs full test suite (~15s) — the gate hole that hid this.
  4. CI immediately caught 2 more env-dependent tests: LSP write-path crash
     now translates to LspError (production fix); external-fixture impl-check
     test skips when the other repo is absent.
- Full suite: 824 passed locally; CI full-suite step green.

## Release v0.11.0 (phase 13)

- PRs #11 (llm_mode parity + java) + #12 (test-debt + full-suite CI) + #13
  (review-findings fail-closed hardening + SPDX license) merged; release
  commit 0e113a0; tag v0.11.0 pushed.
- Gates: no incidents; readiness `readiness-audit:uzjRKCbl3b5Co98KXJd_rsw2`
  (S3/22, no drift/regression); make verify exit 0 (incl. full suite) on
  release commit; HCS `.agent/eval/hcs-release-v0.11.0.md`; HC3 ("release").
- CI: publish + verify green. PyPI page carries License-Expression: MIT.
- Local: pipx 0.10.0 → 0.11.0; config validate ok; SPDX license confirmed.
- Next queue: schema-drift CI guardrail, trajectory-memory relabeller MCP
  parity, stale completeness-report doc sweep. Parked: LLM re-audit, Vul4J,
  HER, language toolchains.

## Queue items 2 (phase 14)

- PR #14 (agent/queue-items-2), 3 commits, CI green (incl. new schema step):
  1. verify-schemas phase + CI step: regenerate exports, fail on schemas/
     drift; self-restoring make phase. Kills the exporter-newline bug class.
  2. relabel_trajectory MCP tool: Agent-HER hindsight relabelling parity —
     last LLM boundary now has an MCP surface; policy-guarded, llm_mode,
     stores unreviewed hypothesis. 4 new tests.
  3. completeness-report.md superseded banner + corrections table.
- All LLM boundaries now MCP-exposed: contract gen, grounding, synthesis,
  summarizer, patch gen, relabeller.
- Parked: LLM re-audit (runner staged), Vul4J, HER benchmark, language
  toolchains (ts-morph/libclang/JDT).

## Release v0.12.0 (phase 15)

- PR #14 merged (422e194); release commit 2101ffb; tag v0.12.0 pushed.
- Gates: no incidents; readiness `readiness-audit:SpiB-lWG_ktJv8cTzPuYWawH`
  (S3/22, no drift/regression); make verify exit 0 (incl. verify-schemas +
  full suite); HCS `.agent/eval/hcs-release-v0.12.0.md`; HC3 approval.
- CI: publish + verify green. Local: pipx 0.11.0 → 0.12.0; config validate ok.
- All LLM boundaries MCP-exposed; schema-drift guard live in verify chain.
- Everything remaining is parked on external deps (key/data/toolchains).

## Coverage gate (phase 16)

- PR #15 (agent/coverage-gate), CI green incl. new coverage step.
- Reconsidered "what's left without a key": confirmed 541 unknowns are
  genuinely LLM-gated (81/82 normative unknowns are prose, no code ref —
  improving heuristics would false-ground). The real no-dep win was the
  THIRD unenforced-gate hole: fail_under=85 declared, never run.
- stdio_transport.py (primary MCP path) 0% → 94%, 14 new tests
  (_handle every method + run_stdio loop over real pipes).
- CI full-suite step now runs --cov --cov-fail-under=85; total 90.8%.
- After this: genuinely all remaining work is key/data/toolchain-gated.

## Remaining risk / uncertainty

- 541 unknown clauses ungrounded without LLM-in-loop re-run; sampled 12, others
  unexamined individually.
- Budget-notification → run-event persistence unverified (confidence 0.6).
- `manifest_regression_verdict: not_run` in impl-check report (covered separately
  by green `tests/harness/test_manifest_regression.py` in verify-tests).
