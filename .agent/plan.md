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

## Phase 9 session addendum

### Verification
- [x] Focused FL tests - `python -m pytest tests/fl` passed with 16 tests.
- [x] MCP/migration regressions - `python -m pytest tests/mcp_server/test_prompts_regressions.py tests/mcp_server/test_tools_tasks_notifications.py tests/storage/test_migrations_transactions.py` passed with 12 tests.
- [x] Full pytest - `python -m pytest` passed with 336 tests.
- [x] Strict changed-file lint/type slice - `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/llm_sca_tooling/fl src/llm_sca_tooling/mcp_server/tools/fl.py tests/fl` and `UV_CACHE_DIR=/tmp/uv-cache uv run mypy src/llm_sca_tooling/fl src/llm_sca_tooling/mcp_server/tools/fl.py` passed.
- [x] Local verify prefix - `make verify` passed isort, Black, Ruff, import-linter, full mypy, unit tests, and detect-secrets.
- [x] Remaining local gates after dependency-audit stop - `make sast schema-check manifest-regression harness-validate` passed.
- [ ] Dependency audit - `make verify` stops at `UV_CACHE_DIR=/tmp/uv-cache uv run pip-audit` because the sandbox cannot resolve `pypi.org`.

### Decisions log
- 2026-05-09T13:20:00Z - Add Phase 9 as a new `llm_sca_tooling.fl` layer below MCP so the fault-localisation pipeline can depend on graph, SARIF, blame, and storage services without importing MCP handlers.
- 2026-05-09T13:20:00Z - Activate the embedding boundary and `fastembed` dependency now, but keep runtime embedding optional through the null adapter so CI and offline runs retain the keyword/graph/SARIF/blame path.
- 2026-05-09T13:20:00Z - Store `get_relevant_files` context bundles as artifact refs and keep the private `investigate` prompt out of the public prompt registry until the Phase 13 repair workflow consumes it.

## Phase 10 session addendum

### Verification
- [x] Phase 10 targeted tests - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/evaluation tests/mcp_server/test_prompts_regressions.py tests/storage/test_workspace_store.py -q` passed with 19 tests.
- [x] Full pytest - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q` passed.
- [x] Changed-slice lint/type - `uv run ruff check src/llm_sca_tooling/evaluation src/llm_sca_tooling/mcp_server/tools/eval.py src/llm_sca_tooling/mcp_server/resources/eval.py tests/evaluation` and `uv run mypy src/llm_sca_tooling/evaluation src/llm_sca_tooling/mcp_server/tools/eval.py src/llm_sca_tooling/mcp_server/resources/eval.py` passed.
- [x] Strict local verify prefix - `make verify` passed isort, Black, Ruff, import-linter, full mypy, unit tests, and detect-secrets.
- [x] Remaining local gates after dependency-audit stop - `make sast schema-check manifest-regression harness-validate` passed.
- [ ] Dependency audit - `make verify` stops at `UV_CACHE_DIR=/tmp/uv-cache uv run pip-audit` because the sandbox cannot resolve `pypi.org`.

### Decisions log
- 2026-05-09T13:50:00Z - Implement Phase 10 as a null-mode local baseline over five smoke fixtures so the evaluation harness is reproducible without external benchmark, network, or LLM calls.
- 2026-05-09T13:50:00Z - Move the import-linter evaluation layer below MCP and keep evaluation modules free of direct `fl` imports; MCP tools/resources may call the evaluation harness, while evaluation remains decoupled from Phase 9 internals.
- 2026-05-09T13:50:00Z - Store eval-run records in a dedicated `eval_runs` table and link eval artefacts through the eval artefact manifest because the shared artifact `run_id` column is constrained to workflow `run_records`.

## Phase 11 session addendum

### Verification
- [x] Phase 11 targeted tests - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/patch_review -q` passed with 108 tests.
- [x] Coverage - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/patch_review --cov=llm_sca_tooling.patch_review` reported 98.33% (every module ≥92%).
- [x] Full pytest - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q` passed.
- [x] Changed-slice lint/type - `uv run ruff check src tests` and `uv run mypy src/llm_sca_tooling/patch_review` clean.

### Decisions log
- 2026-05-09T14:30:00Z - Implement Phase 11 as a self-contained `patch_review/` package: deterministic 8-rule risk policy, SARIF/test/interface deltas, DryRUN contract, scope audit, maintainability gate (Phase 10 oracle), four-agent audit + Sampling fallback, and `run_patch_review`/`classify_patch_risk` MCP tools.
- 2026-05-09T14:30:00Z - Use a heuristic AST diff (regex over hunks) rather than introducing a Tree-sitter dependency; the gate accepts `fallback=True` features and surfaces the limitation in the report.
- 2026-05-09T14:30:00Z - Keep MCP tool handlers synchronous (`asyncio.run` wraps the async orchestrator) to match the existing tool registry contract; expose async `run_patch_review`/`classify_patch_risk` for direct callers.
- 2026-05-09T14:30:00Z - Ship the trained classifier as advisory-only behind the calibration gate (macro-F1 ≥ 0.75 ∧ ECE ≤ 0.10) and family match; deterministic policy is the single source of merge gating until calibration evidence exists.
- 2026-05-16T00:00:00Z - Implement Phase 12 (`sast_repair/`) as a self-contained PredicateFix-style alert-repair loop: alert binding → classification → predicate metadata + retrieval → repair context → patch generation (null-adapter default) → sandbox apply → analyser rerun → SARIF delta verify → build/test rerun → remaining-risk notes → SASTRepairReport + HCS, plus `run_sast_repair` / `get_predicate_examples` / `evolve_static_rules` MCP tools and a `sast-repair.SKILL.md`.
- 2026-05-16T00:00:00Z - Keep all external boundaries (LLM patch generator, analyser rerun, build/test) behind injected callables / ABCs (`PatchGeneratorInterface`, `RerunCallable`, `BuildTestRunner`, `CleanCorpusAdapter`) so HC5 (no-network) and HC6 (no-Red-data) remain trivially satisfied and tests can pin behaviour deterministically.
- 2026-05-16T00:00:00Z - `evolve_static_rules` ships as an explicit `not_implemented_in_phase_12` stub that documents its promotion gate (≥10pp FP reduction at k=5, zero TP loss, reviewable candidate, offline workspace), so the surface exists without enabling rule mutation in this phase.
- 2026-05-16T00:00:00Z - Suppression proposals always set `reviewer_required=True` and require analyser-or-parser-grade classification confidence; the orchestrator skips repair (and sandbox / rerun) when a suppression-eligible FP is found unless `generate_patch=True`, mapping that case to `Verdict.FALSE_POSITIVE_SUPPRESSED`.

## Phase 13 session addendum

### Verification
- [x] Phase 13 targeted tests - `UV_CACHE_DIR=/home/grammy-jiang/.cache/uv uv run pytest tests/workflows/ -q` passed with 121 tests.
- [x] Coverage - `UV_CACHE_DIR=/home/grammy-jiang/.cache/uv uv run pytest --cov=llm_sca_tooling.workflows.bug_resolve tests/workflows/` reported 96.70% total (every module ≥90%).
- [x] Full pytest - `UV_CACHE_DIR=/home/grammy-jiang/.cache/uv uv run pytest --no-header` passed with 671 tests (550 baseline + 121 new).
- [x] Changed-slice lint/type - `uv run ruff check` and `uv run mypy` clean on all new modules.

### Decisions log
- 2026-05-16T00:00:00Z - Implement Phase 13 `workflows/bug_resolve/` as a ten-stage state machine: `state_machine.py` orchestrates all stages; all stage logic lives in single-purpose modules reusing FL (Phase 9), patch_review (Phase 11), sast_repair (Phase 12) callables via injected interfaces.
- 2026-05-16T00:00:00Z - Null mode uses deterministic null gate callables (always pass) and the NullCandidatePatchGenerator so the full pipeline can be tested end-to-end without LLM or external tools; `WorkflowConfig.null_mode=True` is the switch.
- 2026-05-16T00:00:00Z - `generated_test_is_hard_evidence` requires pre_fix_result=FAIL AND fails_for_expected_reason=True AND flaky_flag=False; this rule is enforced in `reproduction_test.py` and tested explicitly.
- 2026-05-16T00:00:00Z - `BugResolveReport.recommendation = merge-supporting` requires process_compliant=True AND all hard gates pass AND selected patch exists; any deterministic gate failure, budget exhaustion, or process violation produces `block`.
- 2026-05-16T00:00:00Z - `run_issue_resolution` MCP tool wraps the async workflow with `asyncio.run()` following the existing patch_review tool pattern; `SideEffectClass.READ_ONLY` is used because the workflow itself does not write to the repo root (only artifact store writes via workspace API).
- 2026-05-16T00:00:00Z - Phase 13 blast-radius stub always sets `is_partial=True`; full cross-repo/cross-language traversal is deferred to Phase 15 per plan.

## Phase 14 session addendum

### Verification
- [x] Phase 14 targeted tests - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/workflows/impl_check/ -q` passed with 90 tests.
- [x] Coverage - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --cov=llm_sca_tooling.workflows.impl_check tests/workflows/impl_check/` reported 98.67% total (all modules ≥90%).
- [x] Full pytest - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --no-header` passed with 761 tests (671 baseline + 90 new).
- [x] Changed-slice lint/type - `uv run ruff check` and `uv run mypy` clean on all new modules.

### Decisions log
- 2026-05-16T00:00:00Z - Implement Phase 14 `workflows/impl_check/` as a seven-stage DAG: ingestion → clause extraction → intent graph → contract generation → grounding → static verdict (Stage 5 + 6a) → dynamic hook (Stage 6b stub) → aggregation → verdict matrix → report assembly. Each stage is a self-contained module.
- 2026-05-16T00:00:00Z - `HarnessPolicyClause` inherits from `Clause` (Pydantic v2 model inheritance) adding four additional fields; `harness_policy_flag` is always True for instances.
- 2026-05-16T00:00:00Z - Compound clause splitting heuristic requires ≥3 parts split on "and" OR exactly 2 parts both containing obligation keywords, to avoid over-splitting natural language; simpler clauses remain atomic=True.
- 2026-05-16T00:00:00Z - Stage 6b `DynamicVerdictRecord` returns `available=False` unconditionally in Phase 14; the hook callable interface (`trace_capture_fn`) is reserved for Phase 16 integration.
- 2026-05-16T00:00:00Z - Auto-pass gate requires `calibration_ece <= 0.10`, at least one strong Stage 5 verdict, no violations, and `risk_class` not `security` or `compliance`; absent calibration data → `auto_pass_gate_passed=False`.
- 2026-05-16T00:00:00Z - `RunImplementationCheckTool` MCP tool wraps the async workflow with `asyncio.run()` following the existing Phase 13 `run_issue_resolution` pattern and is registered in `default_tool_handlers()`.
- 2026-05-16T00:00:00Z - `.skills/audit.SKILL.md` extended with implementation-check mode section documenting `audit(mode="implementation_check")` workflow steps.

## Phase 15 session addendum

### Verification
- [x] Phase 15 targeted tests - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/blast_radius/ -q` passed with 129 tests.
- [x] Coverage - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --cov=llm_sca_tooling.blast_radius tests/blast_radius/` reported 96.61% total (all modules ≥90%).
- [x] Full pytest - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --no-header` passed with 890 tests (761 baseline + 129 new).
- [x] Changed-slice lint/type - `ruff check` and `mypy` clean on all 14 source files in `llm_sca_tooling.blast_radius`; `ruff format` applied to all blast_radius files.
- [!] `make verify` isort/ruff-format failures exist in pre-existing files (`mcp_server/tools/core.py`, `patch_review.py`, `tests/sast_repair/`, `tests/workflows/`) — not introduced by Phase 15. Blast_radius slice is fully clean.

### Decisions log
- 2026-05-17T00:00:00Z - Phase 15 `BlastRadiusService` is a standalone async service in `src/llm_sca_tooling/blast_radius/`; no new MCP tool added per plan spec. Consumed internally by issue-resolution/patch-review workflows via DI.
- 2026-05-17T00:00:00Z - SQLite graph_store is not thread-safe; removed `loop.run_in_executor()` wrappers and run BFS traversal synchronously. This avoids `sqlite3.ProgrammingError` from cross-thread SQLite access.
- 2026-05-17T00:00:00Z - MIXED change type with empty `applicable_types` falls back to `PUBLIC_API_CHANGE` policy (max_hops=5, conservative) rather than INTERNAL (max_hops=3) to avoid under-reporting impact when change type is uncertain.
- 2026-05-17T00:00:00Z - ABI analysis always produces an `UNKNOWN` note when clangd is absent (never silent skip) so the report always surfaces the analysis gap explicitly.
- 2026-05-17T00:00:00Z - Ambiguous links are structurally separate from `impact_groups` in `BlastRadiusReport`; edges below analyser_threshold (0.75) become `AmbiguousLinkRecord` entries, not confirmed `ImpactRecord` entries.
- 2026-05-17T00:00:00Z - `is_partial` is set only when cross-repo traversal is requested but no registered repos are available; it is NOT set always (unlike Phase 13 stub which always set it).
- 2026-05-17T00:00:00Z - `BlastRadiusStub` (Phase 13) retained in `workflows/bug_resolve/` for backward compatibility; Phase 15 `BlastRadiusService` is wired separately. No breaking change to existing workflow state models.

## Phase 16 session addendum

### Verification
- [x] Phase 16 targeted tests - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/traces -q` passed with 14 tests.
- [x] Related workflow regressions - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/traces tests/workflows/impl_check/test_dynamic_verdict.py tests/workflows/bug_resolve/test_gate_runner.py tests/workflows/bug_resolve/test_models.py tests/patch_review/test_dryrun.py tests/patch_review/test_models.py -q` passed with 54 tests.
- [x] Changed-slice lint/type - `ruff check` and `mypy` passed on `llm_sca_tooling.traces`, the `capture_trace` MCP tool, and touched Phase 11/13/14 workflow models.
- [x] Import architecture - `UV_CACHE_DIR=/tmp/uv-cache uv run lint-imports` passed after placing `mcp_server` above `workflows` and adding `traces` as a lower evidence layer.
- [x] Full pytest - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --no-header` passed with 904 tests.

### Decisions log
- 2026-05-17T00:00:00Z - Implement Phase 16 as `llm_sca_tooling.traces`: typed `TraceRunContract`, mandatory `ScopeFilter`, `RawTraceArtefact`, `CompressedTrace`, state-diff/divergence models, sys.settrace Python adapter, JS/TS and C/C++ placeholders, and a deterministic `NullTraceSummarizer` as the LLM boundary.
- 2026-05-17T00:00:00Z - Run Python trace capture through an isolated helper process using `asyncio.create_subprocess_exec`, so timeouts can terminate the traced command while raw JSONL events remain scoped to the workspace artefact root.
- 2026-05-17T00:00:00Z - Keep raw trace JSONL out of MCP payloads; `capture_trace` returns typed run metadata plus compressed trace evidence and stores raw events as `ArtifactKind.TRACE`.
- 2026-05-17T00:00:00Z - Preserve Phase 14 non-reproducing semantics: non-reproducing dynamic traces set `non_reproducing=True` and keep `DynamicVerdictRecord.verdict=unknown`, never satisfied.
- 2026-05-17T00:00:00Z - Correct the import-linter layer order to match the implemented Phase 13/14 MCP-to-workflow dependency: `mcp_server` sits above `workflows`, while `traces` is a lower evidence layer consumed by both.

## Phase 17 session addendum

### Verification
- [x] Phase 17 targeted tests - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory -q` passed with 14 tests.
- [x] Changed-slice lint/type - `ruff check` and `mypy` passed on `llm_sca_tooling.memory`, memory MCP tools, and the memory resource.
- [x] Import architecture - `UV_CACHE_DIR=/tmp/uv-cache uv run lint-imports` passed with `memory` placed below `workflows` as a governed evidence layer.
- [x] Storage/MCP regressions - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory tests/storage/test_workspace_store.py tests/storage/test_migrations_transactions.py tests/mcp_server/test_tools_tasks_notifications.py tests/mcp_server/test_resources.py -q` passed with 29 tests.
- [x] Full pytest - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --no-header` passed with 918 tests.

### Decisions log
- 2026-05-17T00:00:00Z - Implement Phase 17 as opt-in, schema-grounded workspace memory under `llm_sca_tooling.memory`; default policy remains disabled, and memory hints remain zero-weight until the ship gate passes.
- 2026-05-17T00:00:00Z - Add SQLite migration `0005_memory.sql` for policies, trajectories, project memory records, operational lessons, and compaction reports, while keeping payloads as strict Pydantic JSON for schema evolution.
- 2026-05-17T00:00:00Z - Enforce memory write-path gates before persistence: opt-in, required structured fields, forbidden raw artefact references, secret scan, contradiction diagnostics, and `review_state=unreviewed` on trajectory writes.
- 2026-05-17T00:00:00Z - Implement retrieval as deterministic coarse/fine matching with a misalignment guard; rejected records are returned with reasons rather than silently dropped.
- 2026-05-17T00:00:00Z - Keep hindsight relabelling and lesson promotion deterministic/null-mode in Phase 17: relabelled records remain unreviewed, and operational lesson promotion requires explicit `review_approved=True`.
- 2026-05-17T00:00:00Z - Expose `retrieve_memory`, `record_trajectory`, `memory_compact`, `promote_operational_lesson`, and `code-intelligence://memory/{repo}/trajectories`; the resource returns aggregate metadata only, never trajectory content.

## Phase 18 session addendum

### Verification
- [x] Phase 18 targeted tests - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/release -q` passed with 11 tests.
- [x] Changed-slice lint/type - `ruff check` and `mypy` passed on `llm_sca_tooling.release`, T3/T4 runners, operational/readiness MCP tools, prompt registry, and release-gate CLI changes.
- [x] Import architecture - `UV_CACHE_DIR=/tmp/uv-cache uv run lint-imports` passed with `release` placed below `memory` and above `evaluation`.
- [x] Prompt/tool/CLI regressions - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/release tests/mcp_server/test_prompts_regressions.py tests/unit/test_cli.py -q` passed with 16 tests.
- [x] Full pytest - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --no-header` passed with 929 tests.

### Decisions log
- 2026-05-17T00:00:00Z - Implement Phase 18 as a deterministic release layer under `llm_sca_tooling.release`: calibration, ablation, operational harness gates, adversarial checks, production eval refresh, report templates, and release-gate aggregation.
- 2026-05-17T00:00:00Z - Add T3/T4 fixture runners that produce stored `EvalRun` records without network or LLM calls; T3 covers cross-language/blast-radius metrics and T4 covers implementation/spec calibration metrics.
- 2026-05-17T00:00:00Z - Release-gate CLI writes a machine-readable JSON report and exits non-zero when required gates fail; disabled gates are represented explicitly in `ReleaseGateResult` inputs.
- 2026-05-17T00:00:00Z - Graduate `run_operational_review` and `run_readiness_audit` from prompt-only stubs to task-capable MCP tools returning typed Phase 18 reports.
- 2026-05-17T00:00:00Z - Replace `operational-review` and `readiness-audit` prompt stubs with public prompts that reference the implemented launchers, evidence expectations, verdict classes, readiness thresholds, and HCS requirements.

## Phase 19 session addendum

### Verification
- [x] Phase 19 focused tests - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/hardening tests/privacy tests/operations tests/transport tests/docs tests/packaging tests/unit/test_cli.py -q` passed with 26 tests.
- [x] Changed-slice lint/type - `ruff check` and `mypy` passed on Phase 19 hardening, privacy, operations, transport, CLI, and tests.
- [x] Import architecture - `UV_CACHE_DIR=/tmp/uv-cache uv run lint-imports` passed after adding `transport`, `hardening`, and `privacy` layers.
- [x] Distribution checks - `UV_CACHE_DIR=/tmp/uv-cache uv build`, `uv run evidence-sca --version`, and `uv run llm-sca-tooling --version` passed.
- [x] Full pytest - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --no-header` passed with 952 tests.
- [x] Repo verify - `make verify` passed. The first sandboxed attempt failed at `pip-audit` DNS resolution; the approved network retry passed with no known vulnerabilities and noted the local package is not auditable from PyPI.

### Decisions log
- 2026-05-17T00:00:00Z - Complete Phase 19 as additive operational hardening: six permission profiles, cache invalidation events, graph chunking, file watcher fallback, git-hook installer, subscription recovery, task authorization TTL checks, cumulative-risk monitoring, drift checks, manifest regression, and trace redaction auditing.
- 2026-05-17T00:00:00Z - Add `privacy/`, `operations/ledger_*`, and `transport/` packages for redacted exports, retention decisions, explicit deletion confirmation, hardened HTTP transport validation, and deterministic readiness summaries.
- 2026-05-17T00:00:00Z - Add CLI operator commands `replay`, `diagnose`, and `check-drift`; extend `mcp start --transport http` as a hardened configuration validation path rather than starting a network listener in tests.
- 2026-05-17T00:00:00Z - Provide the devcontainer material as `docs/devcontainer-template.md` instead of writing `.devcontainer/` because the repository edit scope does not allow that path.
- 2026-05-17T00:00:00Z - Add the Phase 19 operator documentation set: installation, quickstart, architecture, plugin authoring, evaluation, harness setup, incident response, and the devcontainer template.
- 2026-05-17T00:00:00Z - Add package distribution metadata, a distribution CI smoke workflow, and `evidence-sca --version` so release artefacts and entrypoints are testable.

## MCP stdio setup session addendum

### Verification
- [x] Repo verify - `make verify` passed on 2026-05-10T22:41:43Z with lint, import-linter, mypy, unit tests, secrets scan, dependency audit, Bandit, schema check, manifest regression, and harness validation.

### Decisions log
- 2026-05-10T22:41:43Z - Use a thread-backed MCP stdio transport for the dev server so JSON-RPC clients can initialize reliably when the default async stdin wrapper blocks in the Python 3.14 sandbox.
- 2026-05-10T22:41:43Z - Keep stdio stdout reserved for protocol messages by moving server logging to stderr and suppressing the FastMCP banner in stdio mode.
- 2026-05-10T22:41:43Z - Configure generated uv MCP commands with `--cache-dir .agent/uv-cache --no-sync`, and update legacy uv MCP entries in place while preserving any existing per-server metadata.
