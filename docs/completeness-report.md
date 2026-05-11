# LLM-SCA Tooling — Completeness Report

> Generated: 2026-05-09 (based on current source state)
> Scope: Phases 0–19 + Phase H0
> Source files: 360 Python files across 30 top-level modules
> Test files: 112 Python test files

---

## 1. Executive Summary

### Overall Completeness: ~78%

The project has substantial, production-quality implementations across all 21
phases. Every designed module namespace exists and is importable. The majority
of functions contain real logic (weighted average: ~78% real functions across
all modules). No phase is entirely missing, and the core data-flow from graph
indexing through MCP exposure through workflow execution is end-to-end
functional.

### Key Strengths

1. **Schemas and storage (Phases 0–2)** are complete with real SQLModel/aiosqlite/NetworkX implementations, proper async patterns, and comprehensive test coverage.
2. **MCP server (Phase 4)** is well-implemented with tool/resource/prompt/task/subscription/sampling infrastructure.
3. **Bug-resolve workflow (Phase 13)** is the most complete end-to-end workflow (87% real functions), with a working 10-stage state machine.
4. **Telemetry and governance (Phase H0)** are fully implemented with live JSONL trace writer, permission profiles, policy evaluator, and harness condition sheets.
5. **SARIF layer (Phase 6)** is well-implemented with real parser, normalizer, binding, delta, and four adapters.
6. **Fault localisation (Phase 9)** has a complete multi-signal ranking pipeline.

### Key Gaps

1. **Language backends (Phase 5)** use pure-Python regex fallbacks instead of the specified language toolchains (ts-morph, libclang, JDT). They produce valid graph facts but at lower fidelity.
2. **Memory relabelling (Phase 17)** uses `NullHindsightRelabeller` — Agent-HER hindsight relabelling is not implemented with an actual LLM boundary.
3. **T3/T4 benchmark runners (Phase 18)** run against deterministic fixtures rather than live benchmark suites. No real external benchmark execution.
4. **Telemetry module** has only 37% real-function coverage — the `telemetry/__init__.py` and background flush logic are largely stubs.
5. **`graph/__init__.py`** is an empty placeholder ("In-memory graph traversal. Populated in Phase 3") — this module was designed to house the NetworkX in-memory layer but graph operations were absorbed into `storage/graph_queries.py` instead.
6. **Plugin backlog sub-plugins** (gRPC, Protobuf, ZeroMQ, MQTT, DBUS) are `NotImplementedError` stubs — specified as backlog items but the per-protocol sub-files from the design are not present.
7. **TypeScript, C++, and Java language servers (LSP)** in the indexing layer are present as adapters but rely on subprocess detection for availability — actual LSP protocol parsing may be incomplete under real-world conditions.

---

## 2. Per-Phase Analysis

---

### Phase 0: Python Package Skeleton

**Design Intent**: Package scaffold (`src/llm_sca_tooling/`), dependency management with uv, test runner (pytest), local verify entrypoint (`make verify`), CI baseline, configuration model, structured logging and error model, skeleton modules, CLI/MCP entrypoints, run-record writer, governance skeleton.

**Implementation Status**: ✅ COMPLETE

**What Exists**:
- `__init__.py` — version export via `importlib.metadata` ✅
- `config.py` — full multi-layer config (TOML/JSON/env) with sub-configs for telemetry, budget, policy, MCP; `redacted()` helper ✅
- `errors.py` — 8-class exception hierarchy with `NotImplementedFeatureError` ✅
- `cli/main.py` — Typer multi-app CLI with sub-commands: config show/validate, harness status, run create, mcp start/serve, release-gate; Rich table output ✅
- `cli/diagnose.py`, `cli/release.py`, `cli/replay.py` — Phase 19 sub-apps ✅
- `telemetry/logging.py` — `get_logger()` with auto-configured StreamHandler, Rich-safe ✅
- `telemetry/trace_writer.py` — thread-safe JSONL writer, redaction, sequence IDs ✅
- `operations/run_records.py` — async file-based RunRecordWriter ✅
- `governance/permissions.py`, `governance/policy.py` — permission profiles, PolicyEvaluator ✅
- `pyproject.toml`, `tox.ini`, `Makefile`, `.pre-commit-config.yaml` ✅
- Unit tests: `tests/unit/` covers config, errors, CLI, telemetry, permissions, policy, run-records, budget ✅

**What's Missing**:
- `graph/__init__.py` is an empty placeholder (3 lines); the design called for "In-memory graph traversal" — this is now in `storage/graph_queries.py` but the namespace is unused.

**Notes**: The CLI is richer than the Phase 0 skeleton specification — it already includes Phase 18/19 sub-commands, indicating forward implementation. Phase 0 deliverables fully met.

---

### Phase 1: Shared Schemas and Evidence Model

**Design Intent**: Versioned, typed Pydantic v2 contracts — graph schema, evidence schema, provenance, verdicts, run records, harness conditions, governance, incidents, readiness, supply chain, patches, operations, memory, SARIF schema, contracts, JSON schema exports.

**Implementation Status**: ✅ COMPLETE

**What Exists**:
- `schemas/base.py` — `StrictModel`, `ExtensibleModel`, `canonical_dumps/loads`, `SCHEMA_VERSION` ✅
- `schemas/evidence.py` — `EvidenceBundle`, `EvidenceItem`, `MissingEvidence`, `StaleEvidence` with real `weakest_strength()` logic ✅
- `schemas/graph.py` — `GraphNodeType` (50+ types), `GraphEdgeType` (30+ types), `GraphNode`, `GraphEdge`, `GraphDiagnostic`, `VALID_EDGE_ENDPOINTS` validator ✅
- `schemas/provenance.py` — `Provenance`, `DerivationType`, `EvidenceStrength`, `SourceSpan`, `RepoRef`, `SnapshotRef` ✅
- `schemas/verdicts.py`, `schemas/patches.py`, `schemas/run_records.py`, `schemas/harness.py`, `schemas/governance.py`, `schemas/incidents.py`, `schemas/readiness.py`, `schemas/supply_chain.py`, `schemas/operations.py`, `schemas/memory.py`, `schemas/contracts.py` ✅
- `schemas/sarif.py` — SARIF schema types ✅
- `schemas/json_schema.py` — JSON schema export functions ✅
- `schemas/validation.py` — schema validation helpers ✅
- Test coverage: 13 test files in `tests/schemas/` covering all schema modules ✅

**What's Missing**:
- Nothing significant. The SARIF schema at `schemas/sarif-schema-2.1.0.json` (referenced in Phase 6) may need to be verified.

**Notes**: 86% real-function implementation rate. The schemas module is the strongest in the codebase.

---

### Phase 2: Local Graph Store and Repository Registry

**Design Intent**: SQLite-backed local persistence — repository registry, graph store (add-node, add-edge, fetch, delete), snapshot ledger, harness metadata store, operational store, artefact registry, workspace accessor, transaction support, migrations, export/import.

**Implementation Status**: ✅ COMPLETE

**What Exists**:
- `storage/sqlite.py` — async engine with WAL/FK/busy_timeout pragmas, StaticPool for tests ✅
- `storage/models.py` — SQLModel table definitions ✅
- `storage/graph_store.py` — write-side: `add_nodes`, `add_edges`, batch upsert, dedup by hash ✅
- `storage/graph_queries.py` — read-side with NetworkX ego-graph, `fetch_by_file`, `fetch_by_span`, `fetch_ego_graph` ✅
- `storage/registry.py` — `RepositoryRegistry` with register/list/get/touch/activate ✅
- `storage/snapshots.py` — snapshot ledger ✅
- `storage/workspace.py` — `WorkspaceStore` aggregating graph/query/registry/snapshots ✅
- `storage/harness_store.py` — harness condition metadata ✅
- `storage/transactions.py` — async transaction context manager ✅
- `storage/migrations.py` — schema migration support ✅
- `storage/artifacts.py`, `storage/export_import.py`, `storage/operations.py` ✅
- `storage/ids.py`, `storage/paths.py`, `storage/errors.py` ✅
- Tests: 7 test files in `tests/storage/` covering graph store, registry, snapshots, transactions, workspace ✅

**What's Missing**:
- Nothing significant.

**Notes**: 80% real-function rate. Full async SQLite with proper pragmas. NetworkX used for in-memory traversal at query time.

---

### Phase 3: Repository Indexing MVP

**Design Intent**: Python-focused indexing pipeline — file tree scanner, git metadata (log/blame/status), build/test evidence detection, universal ctags adapter, tree-sitter adapter, Python AST indexer, graph pipeline (merge/dedup), lazy symbol-summary cache, graph manifests, graph slice generator, `graph_build` and `graph_update` service, incremental update support, blame-chain records.

**Implementation Status**: ✅ COMPLETE (with minor gaps)

**What Exists**:
- `indexing/scanner.py` — `FileScanner` with ignore policy, repo/directory/file node emission ✅
- `indexing/git_metadata.py` — git log, blame, status integration via subprocess ✅
- `indexing/blame.py` — blame-chain record model and collector ✅
- `indexing/build_evidence.py` — build/test evidence detection ✅
- `indexing/backends/ctags.py` — universal ctags subprocess adapter ✅
- `indexing/backends/tree_sitter.py` — tree-sitter Python binding adapter ✅
- `indexing/backends/python_ast.py` — Python AST indexer ✅
- `indexing/pipeline.py` — merge/dedup with stronger-provenance selection ✅
- `indexing/service.py` — `IndexingService` orchestrating full build and incremental update ✅
- `indexing/summaries.py` — lazy symbol-summary cache with git_sha invalidation ✅
- `indexing/manifests.py` — graph manifest records ✅
- `indexing/graph_slices.py` — `GraphSliceGenerator` ✅
- `indexing/snapshots.py`, `indexing/hashing.py`, `indexing/ignore.py`, `indexing/provenance.py`, `indexing/config.py`, `indexing/diagnostics.py`, `indexing/result.py` ✅
- Tests: 12 test files in `tests/indexing/` ✅

**What's Missing**:
- `graph/__init__.py` remains empty — this was the intended in-memory NetworkX layer (now lives in `storage/graph_queries.py`).
- `indexing/lsp/` exists but was not in the Phase 3 spec (it's Phase 5 material — included here).

**Notes**: 59% real-function rate in the `indexing` module overall, but this is partly because backend sub-packages (Phase 5) bring stubs that count against Phase 3's raw percentage.

---

### Phase 4: MCP Server Core

**Design Intent**: MCP server with resource routing (repos, schema, graph, slice, summary, blame, build-evidence), tools (register_repo, graph_build, graph_update, plugin_reload, get_graph_slice, find_callers, find_callees, git_blame_chain), prompt stubs (implementation-check, bug-resolve, patch-review, operational-review, readiness-audit), task manager with persistence/polling/TTL/restart, resource subscriptions and notifications, permission descriptors, capability negotiation (MCP Sampling), tool telemetry.

**Implementation Status**: ✅ COMPLETE (with missing sub-resource files)

**What Exists**:
- `mcp_server/server.py` — `MCPServer` with async `initialize()`, FastMCP integration, health_check tool ✅
- `mcp_server/tools.py` — rich `register_core_tools()` including graph_build, graph_update, get_graph_slice, find_callers, find_callees, git_blame_chain, plugin_reload, run_static_analysis, run_patch_review, classify_patch_risk, answer_repo_question, get_relevant_files, run_issue_resolution, run_sast_repair, capture_trace, retrieve_memory, record_trajectory, and more ✅
- `mcp_server/resources.py`, `mcp_server/resource_registry.py`, `mcp_server/resource_uris.py` ✅
- `mcp_server/tool_registry.py`, `mcp_server/tool_permissions.py` ✅
- `mcp_server/prompts.py` — `PromptRegistry` with default prompts ✅
- `mcp_server/tasks.py` — `TaskManager` with TTL, cancellation, progress, persistence ✅
- `mcp_server/subscriptions.py` — `SubscriptionManager` ✅
- `mcp_server/notifications.py` — update notification support ✅
- `mcp_server/telemetry.py` — tool telemetry hooks ✅
- `mcp_server/sampling.py` — MCP Sampling capability negotiation ✅
- `mcp_server/serialization.py`, `mcp_server/context.py`, `mcp_server/config.py`, `mcp_server/errors.py` ✅
- Tests: `tests/mcp_server/`, `tests/unit/test_mcp_server.py` ✅

**What's Missing**:
- Phase 4 design specified a flat `mcp_server/resources/` and `mcp_server/tools/` sub-package layout; instead resources and tools are implemented as flat module files (`resources.py`, `tools.py`) — functionally equivalent but different layout.
- `mcp_server/task_store.py`, `task_runner.py`, `task_ids.py`, `dev_server.py` — referenced in design but not present as separate files (integrated into `tasks.py` and `server.py`).
- Phase 4 prompt `.md` templates (under `mcp_server/prompts/`) are not present as files.

**Notes**: 82% real-function rate. The `tools.py` module is very large (it includes handlers for all phases 4–17). Phase 4 is over-built relative to its own specification because later phases added tools to this module.

---

### Phase 5: Language Backend Expansion

**Design Intent**: Python backend with pyan3 call-graph + Pyright LSP; TypeScript backend with ts-morph, madge, package metadata, test-runner detection; C/C++ backend with libclang, clangd LSP, compile_commands.json, CMake File API, CTest; optional Java backend; shared LSP abstraction layer; backend capability registry; cross-backend fact reconciler; incremental update hooks.

**Implementation Status**: ⚠️ PARTIAL (all backends present but use Python fallbacks)

**What Exists**:
- `indexing/backends/python/python_backend.py` — orchestrates AST + pyan3 + Pyright; pyan3 falls back to AST when CLI unavailable ✅
- `indexing/backends/python/pyan3_adapter.py` — pyan3 availability check + AST fallback ✅
- `indexing/backends/python/pyright_adapter.py` — Pyright subprocess adapter ✅
- `indexing/backends/typescript/ts_backend.py` — **Python regex fallback** (not ts-morph); parses `.ts/.js` with regex for functions, classes, imports ⚠️
- `indexing/backends/typescript/package_meta.py`, `ts_test_detection.py` ✅
- `indexing/backends/cpp/cpp_backend.py` — **Python regex fallback** (not libclang); header/include/class/function detection ⚠️
- `indexing/backends/cpp/compile_commands.py`, `ctest_detection.py` ✅
- `indexing/backends/java/java_backend.py` — **Python regex fallback**; capability-gated ⚠️
- `indexing/backends/java/capability.py` ✅
- `indexing/lsp/client.py`, `protocol.py`, `lifecycle.py`, `request_dispatcher.py`, `capabilities.py`, `errors.py` — shared LSP JSON-RPC layer ✅
- `indexing/backends/base.py`, `capability.py`, `registry.py`, `cross_check.py`, `fact_reconciler.py` ✅
- Tests: `tests/indexing/test_phase5_backends.py`, `test_phase5_lsp.py` ✅

**What's Missing**:
- `ts-morph` Node.js adapter (TypeScript backend uses Python regex, not ts-morph)
- `madge` adapter (TypeScript dependency graph via madge not implemented)
- `module_resolver.py` (TypeScript module resolution)
- `libclang_adapter.py` / `clangd_adapter.py` (C++ uses Python regex, not libclang/clangd)
- `cmake_backend.py` (CMake File API integration)
- `abi_edge_builder.py` (C++ ABI edge building)
- `jdt_adapter.py` (Java JDT LSP adapter)
- Language-specific test detection for TypeScript (`module_resolver.py`) and C++ (`cmake_backend.py`)

**Notes**: All backends produce valid graph facts but at "parser" confidence rather than "analyser" confidence because they use regex rather than actual AST tools. The backend version strings say "phase5-python-fallback" indicating this is acknowledged. LSP abstraction layer is fully implemented and ready for real server integration.

---

### Phase 6: SARIF and Static Analysis Layer

**Design Intent**: SARIF v2.1.0 data model, parser, severity/rule-family normalizer, run store, alert fingerprinting, alert-to-graph binding, `warned_by` edges, Semgrep adapter, Bandit adapter, optional CodeQL adapter, optional external/SonarQube import, SARIF delta utility, `run_static_analysis` MCP tool, `code-intelligence://sarif/{repo}/{run_id}` resource.

**Implementation Status**: ✅ COMPLETE

**What Exists**:
- `sarif/models.py` — full SARIF v2.1.0 model hierarchy (SarifLog, SarifRun, SarifTool, SarifResult, etc.) ✅
- `sarif/parser.py` — JSON validation + version check + structured parse ✅
- `sarif/normalizer.py` — severity and rule-family normalization ✅
- `sarif/fingerprint.py` — deterministic alert fingerprinting ✅
- `sarif/store.py` — SARIF run store ✅
- `sarif/binding.py` — `bind_sarif_run()` async function binding alerts to graph file/symbol nodes ✅
- `sarif/warned_by.py` — `warned_by` edge emitter ✅
- `sarif/delta.py` — before/after SARIF delta utility ✅
- `sarif/resource.py`, `sarif/service.py` — MCP resource and service ✅
- `sarif/adapters/semgrep.py`, `bandit.py`, `codeql.py`, `external_import.py`, `sonarqube.py`, `ruleset.py`, `base.py` ✅
- Tests: `tests/sarif/test_phase6_sarif.py` ✅

**What's Missing**:
- The Phase 6 design referenced `schemas/sarif-schema-2.1.0.json` for jsonschema validation; the current `sarif/parser.py` uses an inline minimal schema dict (not the full SARIF v2.1.0 JSON Schema). This is a fidelity gap for strict schema validation.

**Notes**: 80% real-function rate. All specified adapters present and functional.

---

### Phase 7: Cross-Language Interface Plugin System

**Design Intent**: Plugin base with `detect/index/link/traverse` methods, `InterfaceRecord`/`InterfaceOperation` models, plugin registry, cross-language traversal engine, HTTP-REST MVP (OpenAPI parser, FastAPI/Flask/Django detection, JS/TS client detection, URL normalization), WebSocket MVP (socket.io server/client event detection), omniORB-IDL MVP, backlog stubs (gRPC/Protobuf/ZeroMQ/MQTT/DBUS), `trace_cross_language` and `plugin_reload` MCP tools, `code-intelligence://interfaces` resources.

**Implementation Status**: ⚠️ PARTIAL

**What Exists**:
- `plugins/base.py` — `InterfacePluginBase` ABC with four abstract methods, `TraversalDirection`, `AmbiguousLinkRecord` ✅
- `plugins/interface_record.py` — `InterfaceRecord`, `InterfaceOperation`, `InterfaceKind` ✅
- `plugins/registry.py` — `PluginRegistry` with `build_default_registry()` ✅
- `plugins/capability.py` — `PluginCapabilityDescriptor` ✅
- `plugins/traversal.py` — `CrossLanguageTraverser` ✅
- `plugins/graph_facts.py`, `plugins/service.py`, `plugins/store.py` ✅
- `plugins/http_rest/plugin.py` — `HttpRestPlugin` with `detect/index/link/traverse` ✅
- `plugins/http_rest/openapi_parser.py` — OpenAPI/Swagger YAML/JSON parsing ✅
- `plugins/http_rest/url_normalizer.py` — URL path normalization ✅
- `plugins/websocket/plugin.py` — `WebSocketPlugin` with `detect/index/link/traverse` ✅
- `plugins/omniorb_idl/plugin.py` — `OmniOrbIdlPlugin` (basic IDL regex detection) ✅
- `plugins/backlog/__init__.py` — `GrpcStub`, `ProtobufStub`, `ZeroMQStub`, `MqttStub`, `DbusStub` all as `NotImplementedError` stubs ✅ (stubs)
- Tests: `tests/plugins/test_phase7_plugins.py` ✅

**What's Missing**:
- `plugins/http_rest/fastapi_detector.py`, `flask_detector.py`, `django_detector.py` — framework-specific server detectors not implemented as separate modules (basic regex in plugin.py)
- `plugins/http_rest/client_detector.py`, `schema_extractor.py`
- `plugins/websocket/server_detector.py`, `client_detector.py`, `event_extractor.py`, `namespace_resolver.py` — submodule split not done
- `plugins/omniorb_idl/idl_parser.py`, `cpp_servant_linker.py`, `python_stub_linker.py`, `caller_finder.py`, `generated_artifact_tracker.py` — IDL plugin has only one file
- Individual backlog stub files (`grpc_stub.py`, `protobuf_stub.py`, etc.) — consolidated into `backlog/__init__.py`

**Notes**: 54% real-function rate (highest stub concentration). The core plugin contract and three MVP plugins are present but the detailed sub-module decomposition from the design is not implemented.

---

### Phase 8: Repository Query and Repo-QA MVP

**Design Intent**: `QuestionClass` enum (file-loc, symbol-loc, behaviour-trace, contract-check, other), question classifier, deterministic file/symbol lookup, graph-path answer builder, behaviour-trace traversal, interface-contract lookup, git blame chain tool, LLM synthesis boundary, evidence assembler, `classify_repo_question`/`answer_repo_question`/`get_interface_contract`/`git_blame_chain` MCP tools, answer quality gates/ship thresholds.

**Implementation Status**: ⚠️ PARTIAL

**What Exists**:
- `qa/question.py` — `QuestionClass`, `RepoQuestion`, `normalize_question()` ✅
- `qa/classifier.py` — `classify_question()` with deterministic rule-based classification ✅
- `qa/lookup.py` — deterministic file and symbol lookup ✅
- `qa/graph_query.py` — graph-path answer builder ✅
- `qa/behaviour_trace.py` — behaviour-trace graph traversal ✅
- `qa/interface_lookup.py` — interface contract lookup wrapping Phase 7 ✅
- `qa/blame.py` — `BlameResource` ✅
- `qa/evidence_assembler.py` — typed evidence assembler ✅
- `qa/answer.py` — `AnswerModel` with evidence citations ✅
- `qa/confidence.py` — per-question-class confidence rules ✅
- `qa/synthesis.py` — LLM synthesis boundary (stub, returns placeholder) ⚠️
- `qa/service.py` — `answer_repo_question()` orchestration ✅
- `qa/ship_gate.py` — answer quality gates ✅
- Tests: `tests/qa/test_phase8_qa.py` ✅

**What's Missing**:
- `qa/synthesis.py` LLM call is a stub — returns a fixed placeholder text; actual LLM integration not implemented.
- Behaviour-trace answer confidence is conservative (heuristic) — the ≥70% graph-augmented QA ship-gate condition is not enforced.

**Notes**: 74% real-function rate. Structural pipeline is complete; LLM synthesis layer is the main stub.

---

### Phase 9: Fault Localisation

**Design Intent**: Issue text normalizer, keyword retrieval, semantic embedding interface + per-symbol vector cache, SARIF proximity prior, blame/history prior, graph-neighbour expansion, optional SBFL/Ochiai, bounded context assembler (6–10 file budget), per-candidate reasoning chains (RGFL pattern), ranking policy, uncertainty model, `get_relevant_files` MCP tool, private `investigate` template, memory hint integration stub.

**Implementation Status**: ⚠️ PARTIAL

**What Exists**:
- `fl/issue.py` — issue text normalizer with symptoms/APIs/stack trace extraction ✅
- `fl/keyword_retrieval.py` — keyword retrieval against graph index ✅
- `fl/embedding_interface.py` — embedding adapter interface ✅
- `fl/embedding_adapters/null_adapter.py`, `local_adapter.py`, `openai_adapter.py` ✅
- `fl/vector_cache.py` — per-symbol vector cache with git_sha invalidation ✅
- `fl/sarif_prior.py` — SARIF proximity prior ✅
- `fl/blame_prior.py` — blame/history prior ✅
- `fl/graph_expansion.py` — caller/callee/import/test neighbour expansion ✅
- `fl/sbfl.py` — SBFL/Ochiai suspiciousness feature (stub when no coverage data) ✅
- `fl/context_assembler.py` — bounded context assembler (6–10 file budget) ✅
- `fl/ranking.py` — `RankingPolicy` with weighted signal merging ✅
- `fl/reasoning.py` — symbol candidate reasoning chains ✅
- `fl/uncertainty.py` — uncertainty model ✅
- `fl/localisation.py` — `get_relevant_files()` main pipeline ✅
- `fl/investigate.py` — private investigate template ✅
- `fl/memory_stub.py` — memory hint integration (stub returning no hints) ⚠️
- `fl/models.py` — all FL data models ✅
- Tests: `tests/fl/test_phase9_fl.py` ✅

**What's Missing**:
- `fl/memory_stub.py` is a stub — memory hints not populated until Phase 17 is wired in.
- `fl/local_adapter.py` (fastembed) likely needs fastembed installed to be fully functional.
- The reasoning chain (RGFL pattern) in `fl/reasoning.py` returns deterministic heuristics, not LLM-driven reasoning.

**Notes**: 81% real-function rate. Excellent pipeline structure with real signal integration.

---

### Phase 10: Evaluation Harness Baseline

**Design Intent**: Eval run model/records, Harness Condition Sheet model, benchmark adapter interface, local smoke format, T1 smoke runner, T2 regression runner skeleton, FL metrics, RDS v0.2 six-axis feature computation, operational-quality metrics, structural maintainability oracle, AI-readiness report generator, contamination canary, flaky-test detector, repeated-trial skeleton, prompt/manifest/tool regression adapter, `code-intelligence://eval/{run_id}` resource, `run_eval_suite`/`compute_rds_features`/`record_eval_result` tools, `evaluate` template.

**Implementation Status**: ⚠️ PARTIAL

**What Exists**:
- `evaluation/models.py` — `EvalRun`, `EvalInstanceResult`, `EvalStatus` ✅
- `evaluation/harness_condition.py` — `HarnessConditionSheet` and writer ✅
- `evaluation/benchmark_adapter.py` — benchmark adapter interface + `GoldPatchRecord` ✅
- `evaluation/smoke_adapter.py` — `LocalSmokeAdapter` for smoke runs ✅
- `evaluation/t1_runner.py` — T1 null/smoke runner with fixture data ✅
- `evaluation/t2_runner.py` — T2 regression runner with fixture data ✅
- `evaluation/t3_runner.py` — T3 cross-language runner with fixture data (Phase 18) ✅
- `evaluation/t4_runner.py` — T4 spec/implementation runner with fixture data (Phase 18) ✅
- `evaluation/fl_metrics.py` — `top_k_accuracy`, `fl_conditioned_repair_rate` ✅
- `evaluation/rds_features.py` — `compute_rds_features()` ✅
- `evaluation/operational_metrics.py` — `compute_operational_metrics()` ✅
- `evaluation/maintainability_oracle.py` — structural maintainability adapter ✅
- `evaluation/ai_readiness.py` — AI-readiness report generator ✅
- `evaluation/contamination.py` — contamination canary (`unknown_canary()`) ✅
- `evaluation/flaky_detector.py` — flaky-test detection metadata ✅
- `evaluation/replay.py` — repeated-trial / replay skeleton ✅
- `evaluation/regression_adapter.py` — prompt/manifest regression adapter ✅
- `evaluation/artefact_writer.py` — `EvalStore` artefact writer ✅
- `harness/condition.py` — `HarnessConditionWriter` ✅
- Tests: `tests/evaluation/test_phase10_evaluation.py` ✅

**What's Missing**:
- T1–T4 runners use **deterministic fixture data** rather than connecting to real benchmark repositories (SWE-bench, Defects4C, CodeSpecBench). This is by design for local testing but means real benchmark execution is not supported.
- Some evaluation runners have 22 stub functions (65% real rate) — several features degrade gracefully.

**Notes**: 65% real-function rate in evaluation module. The infrastructure is solid; the limitation is the T3/T4 runners requiring live external benchmark data.

---

### Phase 11: Patch Review and Risk Gates

**Design Intent**: Diff parser, changed-symbol detector, AST diff features, graph context extraction, SARIF delta, test delta, vulnerability prior, interface compatibility check, behavioural drift placeholder, MCP Sampling four-agent audit, DryRUN prediction contract, scope/permission audit, structural maintainability gate, patch-risk classifier with typed feature contract, initial deterministic risk policy, four review axes, merge/block recommendation, operational-review integration, `run_patch_review`/`classify_patch_risk` tools, `audit`/`risk-classify` templates.

**Implementation Status**: ⚠️ PARTIAL

**What Exists**:
- `patch_review/diff_parser.py` — unified diff parser ✅
- `patch_review/symbol_detector.py` — changed symbol detector ✅
- `patch_review/ast_diff.py` — AST-level diff features ✅
- `patch_review/graph_context.py` — graph context around changed symbols ✅
- `patch_review/sarif_delta.py` — SARIF before/after delta for patches ✅
- `patch_review/test_delta.py` — test result delta model ✅
- `patch_review/risk_features.py` — `PatchRiskFeatureVector` with 15+ features ✅
- `patch_review/risk_classifier.py` — `classify_patch_risk()` deterministic classifier ✅
- `patch_review/risk_policy.py` — merge/block recommendation policy ✅
- `patch_review/interface_compat.py` — interface compatibility check ✅
- `patch_review/maintainability_gate.py` — structural maintainability gate ✅
- `patch_review/dryrun.py` — `DryRUNPrediction` contract ✅
- `patch_review/four_agent_audit.py` — four-agent audit scaffold ✅
- `patch_review/merge_policy.py` — merge policy model ✅
- `patch_review/scope_audit.py` — scope and permission audit ✅
- `patch_review/sampling_integration.py` — MCP Sampling integration with fallback ✅
- `patch_review/report.py` — `run_patch_review()` orchestration ✅
- `patch_review/operational_integration.py` — operational-review integration ✅
- Tests: `tests/patch_review/test_phase11_patch_review.py` ✅

**What's Missing**:
- `patch_review/four_agent_audit.py` — four-agent audit is scaffolded but the actual multi-agent LLM calls are stubs (returns deterministic mock audit).
- Vulnerability prior / CWE calibration data integration is a stub.
- Behavioural drift check is a placeholder.

**Notes**: 73% real-function rate. Deterministic gates are fully real; LLM-dependent gates are stubs.

---

### Phase 12: Static Analysis Alert Repair

**Design Intent**: Alert binding to graph nodes, rule/predicate metadata extraction, alert explanation generator, alert classification (true/false positive), predicate-example retrieval (PredicateFix), corpus adapter, repair prompt context builder, patch generation interface (LLM boundary), suppression proposal, patch application sandbox, analyser rerun, SARIF delta verification, build/test rerun, remaining-risk notes, offline rule-refinement stub, `run_sast_repair`/`get_predicate_examples` tools, `sast-repair` template.

**Implementation Status**: ⚠️ PARTIAL

**What Exists**:
- `sast_repair/alert_binding.py` — `bind_alert()` linking SARIF alert to graph node ✅
- `sast_repair/alert_classification.py` — classification into likely TP/FP/unknown ✅
- `sast_repair/predicate_metadata.py` — `extract_predicate_metadata()` ✅
- `sast_repair/predicate_examples.py` — `get_predicate_examples()` PredicateFix pattern ✅
- `sast_repair/repair_context.py` — repair context builder ✅
- `sast_repair/corpus_adapter.py` — clean corpus adapter ✅
- `sast_repair/patch_generator.py` — patch generation interface (LLM boundary stub) ⚠️
- `sast_repair/suppression.py` — suppression proposal path ✅
- `sast_repair/sandbox.py` — patch application sandbox ✅
- `sast_repair/analyser_rerun.py` — analyser rerun integration ✅
- `sast_repair/sarif_delta_verifier.py` — SARIF delta verification ✅
- `sast_repair/build_test_runner.py` — build/test rerun integration ✅
- `sast_repair/remaining_risk.py` — remaining-risk notes ✅
- `sast_repair/rule_evolution.py` — offline rule-refinement workflow ✅ (marked as offline)
- `sast_repair/report.py` — `run_sast_repair()` orchestration ✅
- `sast_repair/models.py` ✅
- Tests: `tests/sast_repair/test_phase12_sast_repair.py` ✅

**What's Missing**:
- `sast_repair/patch_generator.py` — actual LLM patch generation is a stub (returns a `NullPatchGenerator` result without calling an LLM).

**Notes**: 65% real-function rate. Infrastructure complete; LLM integration boundary is the main stub.

---

### Phase 13: Bug-Resolve Workflow

**Design Intent**: 10-stage state machine (load, investigate, repair, dryrun, gates, patch_risk, blast_radius, scope_audit, operational_review, trajectory), repair context builder, unified diff generation/validation, pre/postcondition draft, reproduction test, execution-free certificate, gate runner, patch selection, final report + run record + Harness Condition Sheet, session trace/evidence manifest, monitor hooks (loop detection/budget hard-stop), `run_issue_resolution` tool, `bug-resolve` prompt.

**Implementation Status**: ✅ COMPLETE

**What Exists**:
- `workflows/bug_resolve/state_machine.py` — stage transitions, doom-loop check, budget-exhausted transition ✅
- `workflows/bug_resolve/models.py` — `WorkflowState`, `WorkflowConfig`, `BugResolveReport`, `MonitorEvent` ✅
- `workflows/bug_resolve/config.py` — default config ✅
- `workflows/bug_resolve/report.py` — full 10-stage orchestration ✅
- `workflows/bug_resolve/investigate.py` — investigate stage wrapping Phase 9 FL ✅
- `workflows/bug_resolve/repair_context.py` — repair context builder ✅
- `workflows/bug_resolve/candidate_patch.py` — `NullPatchGenerator` (LLM boundary stub) ⚠️
- `workflows/bug_resolve/gate_runner.py` — test/build/SARIF/interface gate runner ✅
- `workflows/bug_resolve/blast_radius_stub.py` — blast-radius integration ✅
- `workflows/bug_resolve/patch_selection.py` — patch selection policy ✅
- `workflows/bug_resolve/preconditions.py` — pre/postcondition draft generation ✅
- `workflows/bug_resolve/reproduction_test.py` — reproduction test support ✅
- `workflows/bug_resolve/certificate.py` — execution-free certificate schema ✅
- `workflows/bug_resolve/trace_manifest.py` — session trace and evidence-manifest writer ✅
- `workflows/bug_resolve/monitor_hooks.py` — doom-loop and snapshot-staleness checks ✅
- Tests: `tests/workflows/bug_resolve/test_phase13_bug_resolve.py` ✅

**What's Missing**:
- `candidate_patch.py` / `NullPatchGenerator` — patch generation uses a null LLM-boundary stub. The patch diff content is placeholder text.

**Notes**: 87% real-function rate — the highest among workflow modules. The workflow structure is genuinely complete including state machine, gate runner, and report assembly. Only LLM inference calls are stubs.

---

### Phase 14: Implementation-Check Workflow

**Design Intent**: 7-stage DAG (ingestion → clause extraction → intent graph → grounding → contract generation → static/dynamic verdict → aggregation), spec/doc ingestion (Markdown), clause model, harness-policy clause, intent graph, clause-to-code grounding, contract artefact generation (Semgrep/pytest/NL probes), static/dynamic verdict runners, ECE gate, clause verdict matrix, `run_implementation_check` tool, `implementation-check` prompt, `audit` template (impl-check mode).

**Implementation Status**: ⚠️ PARTIAL

**What Exists**:
- `impl_check/ingestion.py` — Markdown/plaintext spec document ingestion ✅
- `impl_check/clause_extractor.py` — clause extraction from spec documents ✅
- `impl_check/intent_graph.py` — `IntentGraph` model ✅
- `impl_check/grounding.py` — clause-to-code grounding via repo-QA and graph slices ✅
- `impl_check/contract_generator.py` — contract artefact generation (Semgrep/pytest/NL probes) ✅
- `impl_check/static_verdict.py` — static verdict runner (stages 1–6a) ✅
- `impl_check/dynamic_verdict.py` — dynamic verdict hook (stage 6b) ✅ (stub)
- `impl_check/verdict_matrix.py` — clause verdict matrix ✅
- `impl_check/aggregator.py` — ECE-gated verdict aggregator ✅
- `impl_check/operational_binding.py` — operational evidence binding ✅
- `impl_check/report.py` — `run_implementation_check()` orchestration ✅
- `impl_check/models.py` ✅
- Tests: `tests/impl_check/test_phase14_impl_check.py` ✅

**What's Missing**:
- `impl_check/dynamic_verdict.py` — dynamic verdict hook is a stub (no actual dynamic test execution).
- PDF/HTML ingestion (Phase 14 specified HTML via lxml; only Markdown is implemented).
- ECE gate calibration data not populated (uses placeholder threshold).

**Notes**: 76% real-function rate. Static pipeline is solid; dynamic verdict requires runtime infrastructure.

---

### Phase 15: Cross-Language and Cross-Repository Blast Radius

**Design Intent**: Change-set parser, changed graph node detection, 5 traversal policies by change type, 8 impact groups, generated-stub reporting, C/C++ ABI signature detection, template instantiation impact, ownership/nullness edge traversal, build-target reachability, ambiguous interface candidate bucket, cross-repo graph overlay traversal, human-readable impact report with citations, hardened `blast-radius` template.

**Implementation Status**: ⚠️ PARTIAL

**What Exists**:
- `blast_radius/service.py` — `BlastRadiusService` orchestration ✅
- `blast_radius/models.py` — `BlastRadiusConfig`, `ImpactRecord`, `CrossRepoImpactRecord`, `BlastRadiusReport` ✅
- `blast_radius/change_type.py` — change-type detection from diff ✅
- `blast_radius/traversal_policy.py` — traversal policies by change type ✅
- `blast_radius/graph_traversal.py` — NetworkX multi-hop traversal ✅
- `blast_radius/abi_impact.py` — C/C++ ABI-relevant signature detection ✅
- `blast_radius/impact_groups.py` — 8 impact group classification ✅
- `blast_radius/ambiguous_links.py` — ambiguous link separation ✅
- `blast_radius/cross_repo.py` — cross-repo overlay traversal ✅
- `blast_radius/generated_stub.py` — generated-file impact reporting ✅
- `blast_radius/sarif_reachability.py` — SARIF alert reachability from impact nodes ✅
- Tests: `tests/blast_radius/test_phase15_blast_radius.py` ✅

**What's Missing**:
- Template instantiation impact (C++ template propagation) is a stub.
- Ownership/nullness edge traversal relies on those edge types being populated (Phase 5 backends don't produce them yet).

**Notes**: 83% real-function rate. A well-implemented module with only minor gaps.

---

### Phase 16: Dynamic Trace Augmentation

**Design Intent**: `TraceRunContract` model, Python trace adapter (`sys.settrace`), JS/TS adapter placeholder (Node.js inspector), C/C++ adapter placeholder (sanitizers/rr/gdb), raw trace artefact store, scope filter, LLM trace compression interface, state-diff model, divergence-point model, `CompressedTrace` model, integration hooks into FL/impl-check/bug-resolve/patch-review, `capture_trace` tool.

**Implementation Status**: ⚠️ PARTIAL

**What Exists**:
- `traces/models.py` — `TraceRunContract`, `RawTraceArtefact`, `TraceEvent`, `ScopeFilter`, `StateDiff`, `DivergencePoint`, `CompressedTrace` ✅
- `traces/adapters/python_adapter.py` — `PyTraceAdapter` using `sys.settrace` ✅ (real)
- `traces/adapters/js_adapter.py` — JS/TS adapter placeholder ✅ (raises `NotImplementedError`)
- `traces/adapters/cpp_adapter.py` — C/C++ adapter placeholder ✅ (raises `NotImplementedError`)
- `traces/adapters/registry.py` — adapter registry ✅
- `traces/artefact_store.py` — raw trace artefact storage ✅
- `traces/scope_filter.py` — scope filter engine ✅
- `traces/compression/interface.py` — compression/summarization interface ✅
- `traces/compression/null_summarizer.py` — null LLM-boundary summarizer ⚠️
- `traces/compression/state_diff.py` — state-diff model ✅
- `traces/service.py` — `capture_trace()` orchestration ✅
- `traces/integration/fl_hook.py`, `bug_resolve_hook.py`, `impl_check_hook.py`, `patch_review_hook.py` ✅
- Tests: `tests/traces/test_phase16_traces.py` ✅

**What's Missing**:
- JS/TS trace adapter raises `NotImplementedError` — placeholder only.
- C/C++ trace adapter raises `NotImplementedError` — placeholder only.
- `traces/compression/null_summarizer.py` returns a fixed summary — actual LLM compression not implemented.

**Notes**: 81% real-function rate. Python adapter is fully functional. JS/TS and C/C++ adapters are placeholders as specified.

---

### Phase 17: Trajectory Memory and Experience Replay

**Design Intent**: Memory opt-in policy, schema-grounded project-memory model, trajectory record schema/writer, privacy/retention fields, write-path validation/redaction/secret-scan, coarse retrieval, fine retrieval, misalignment guard, hindsight relabelling (Agent-HER), eviction/retention policy (Evo-Memory), operational lesson promotion, `code-intelligence://memory/{repo}/trajectories` resource, `retrieve_memory`/`record_trajectory`/`memory_compact`/`promote_operational_lesson` tools, memory ship-gate.

**Implementation Status**: ⚠️ PARTIAL

**What Exists**:
- `memory/models.py` — `TrajectoryRecord`, `ProjectMemoryRecord`, `OperationalLesson`, `MemoryOptInPolicy`, `HindsightLabel`, `EvictionPolicy` ✅
- `memory/store.py` — `MemoryStore` in-memory dict store with trajectories/project-records/lessons ✅
- `memory/policy.py` — `make_default_policy()`, `MemoryDisabledError` ✅
- `memory/write_path.py` — `validate_and_write()` with redaction and secret-scan ✅
- `memory/ship_gate.py` — memory ship gate enforcement ✅
- `memory/retrieval/coarse.py` — `retrieve_coarse()` keyword-based retrieval ✅
- `memory/retrieval/fine.py` — `retrieve_fine()` scored fine retrieval ✅
- `memory/retrieval/misalignment_guard.py` — high-similarity/low-utility rejection ✅
- `memory/promotion/pipeline.py` — `promote_lesson()` with review gate ✅
- `memory/relabelling/null_relabeller.py` — `NullHindsightRelabeller` deterministic stub ⚠️
- `memory/eviction/compactor.py` — `compact()` trajectory eviction/retention ✅
- Tests: `tests/memory/test_phase17_memory.py` ✅

**What's Missing**:
- Agent-HER hindsight relabelling only has `NullHindsightRelabeller` — no real LLM relabelling.
- `MemoryStore` is in-memory only; no database-backed persistent store.
- Memory ship-gate delta measurement (HER vs. success-only memory) is not computed against live T2/T3 data.

**Notes**: 83% real-function rate. Structural memory system is solid; LLM-dependent relabelling is the main gap.

---

### Phase 18: Full Evaluation, Calibration, and Release Gates

**Design Intent**: T3 cross-language runner, T4 spec/implementation runner, calibration report pipeline (patch-risk ECE, impl-check ECE), harness ablation runner, operational harness gates, adversarial checks (prompt/document injection, tool-boundary misuse, multi-step policy bypass), production-derived eval refresh, release gate command, full `run_operational_review`/`run_readiness_audit` launchers, public `operational-review`/`readiness-audit` prompts.

**Implementation Status**: ⚠️ PARTIAL

**What Exists**:
- `evaluation/t3_runner.py` — T3 cross-language runner with SWE-PolyBench-style fixtures ✅
- `evaluation/t4_runner.py` — T4 implementation/spec runner with CodeSpecBench/Vul4J-style fixtures ✅
- `release/release_gate.py` — `ReleaseGateEvaluator` + `build_passing_fixture_release_gate()` + CLI command ✅
- `release/calibration.py` — calibration report pipeline + `expected_calibration_error()` ✅
- `release/adversarial.py` — adversarial check suite (prompt injection, tool-boundary misuse, multi-step policy bypass, out-of-scope write) ✅
- `release/ablation.py` — harness ablation runner ✅
- `release/operational_gates.py` — operational harness gates ✅
- `release/operational_review.py` — `run_operational_review()` launcher ✅
- `release/readiness_audit.py` — `run_readiness_audit()` launcher ✅
- `release/models.py` — all Phase 18 data models ✅
- `release/production_refresh.py` — production-derived eval refresh workflow ✅
- `release/report_templates.py` — benchmark report templates ✅
- Tests: `tests/release/test_phase18_release.py`, `tests/evaluation/test_phase18_tiers.py` ✅

**What's Missing**:
- T3 and T4 runners use **local fixture data** only. No actual SWE-PolyBench, Defects4C, or CodeSpecBench dataset connectivity.
- Calibration reports are built from fixture samples; ECE is computed but not against real production runs.
- Memory ship-gate delta is not computed from live runs.

**Notes**: 82% real-function rate. The gate infrastructure is real and the CLI `release-gate` command is functional. The limitation is external benchmark data.

---

### Phase 19: Operational Hardening and Distribution

**Design Intent**: Cache invalidation hardening, file watcher + git hook integration, large graph chunking, resource subscription recovery, task TTL/authorization hardening, permission profile hardening, sandbox/devcontainer templates, session replay + incident-diagnosis tooling, operational ledger retention/export/delete, trace redaction audit, manifest regression test runner, cumulative risk monitoring, harness drift checks, privacy controls (redaction/retention/export-delete), Streamable HTTP transport, packaging and release automation, documentation (7 guides).

**Implementation Status**: ⚠️ PARTIAL

**What Exists**:
- `hardening/cache_invalidation.py` — cache invalidation hardening ✅
- `hardening/file_watcher.py` — `FileWatcherService` + `RepoChangeHandler` with debounce and asyncio dispatch ✅
- `hardening/git_hooks.py` — git hook integration for graph_update ✅
- `hardening/graph_chunker.py` — large graph chunking ✅
- `hardening/subscription_recovery.py` — subscription recovery after disconnect ✅
- `hardening/task_authorization.py` — task TTL/authorization hardening ✅
- `hardening/permission_profiles.py` — permission profile hardening ✅
- `hardening/cumulative_risk.py` — cumulative risk monitoring ✅
- `hardening/harness_drift.py` — harness drift checks ✅
- `hardening/manifest_regression_runner.py` — manifest regression test runner ✅
- `hardening/trace_redaction_audit.py` — trace redaction audit ✅
- `cli/diagnose.py`, `cli/replay.py`, `cli/release.py` — incident-diagnosis and session replay CLI ✅
- `operations/ledger_retention.py`, `ledger_exporter.py`, `ledger_delete.py` — operational ledger tools ✅
- `privacy/redaction.py`, `privacy/retention_policy.py`, `privacy/export_delete.py` ✅
- `transport/http_transport.py` — Streamable HTTP transport with TLS, CORS, auth-token-env support ✅
- `transport/__init__.py` ✅
- Documentation: 7 guide files in `docs/` ✅
- Tests: `tests/hardening/` (11 test files), `tests/privacy/`, `tests/transport/`, `tests/operations/` ✅

**What's Missing**:
- Devcontainer templates (`.devcontainer/`) exist but were Phase H0 artefacts; sandbox templates are not present.
- Phase 19 packaging and release automation (wheel/sdist publishing, GitHub Actions release workflow) not yet finalized.
- `hardening/` module has 15 stub functions (82% real); some edge-case hardening paths are stubs.

**Notes**: 82% real-function rate in hardening. The HTTP transport and most hardening infrastructure is genuinely implemented. Session replay and incident-diagnosis CLIs are present.

---

### Phase H0: Harness Quality Foundation

**Design Intent**: Governance manifests (AGENTS.md), permission profiles, telemetry contracts, verify-before-commit gates (Makefile, pre-commit), harness stage/drift classification, AI-readiness scoring, Harness Condition Sheet, telemetry event types, run-record contract, non-relaxation tests, manifest regression harness, semantic mutation tests.

**Implementation Status**: ✅ COMPLETE

**What Exists**:
- `AGENTS.md` — full governance manifest with HC1–HC6, scope boundary, verify command, PR checklist, stop conditions ✅
- `Makefile` — verify target, conditional steps ✅
- `.pre-commit-config.yaml` — secrets detection, format, lint hooks ✅
- `pyproject.toml` — full dependency declaration, tool configuration ✅
- `tox.ini` — multi-version test matrix ✅
- `governance/permissions.py` — `PermissionProfileLoader`, all 6 permission profiles ✅
- `governance/policy.py` — `PolicyEvaluator` with tool-category/path/network decisions ✅
- `telemetry/trace_writer.py` — live JSONL trace writer with redaction ✅
- `harness/condition.py` — `HarnessConditionWriter` capturing full harness state ✅
- `evaluation/harness_condition.py` — `HarnessConditionSheet` Pydantic model ✅
- `.devcontainer/` — devcontainer configuration ✅
- `.agent/` — plan, docs, templates, skills directories ✅
- `tests/harness/test_non_relaxation.py` — non-relaxation tests checking AGENTS.md constraints ✅
- `tests/harness/test_manifest_regression.py` — manifest regression tests ✅
- `tests/harness/test_semantic_mutation.py` — semantic mutation tests ✅
- Tests: `tests/unit/test_permissions.py`, `test_policy.py`, `test_harness_condition.py`, `test_telemetry.py`, `test_trace_writer.py` ✅

**What's Missing**:
- Nothing significant. Harness quality foundation is complete.

**Notes**: The H0 phase is the best-implemented aspect of the project. Governance, telemetry, and verification infrastructure are production-quality.

---

## 3. Summary Table

| Phase | Name | Status | Files | Avg %Real | Key Gaps |
|---|---|---|---|---|---|
| H0 | Harness Quality Foundation | ✅ COMPLETE | 5+ | ~90% | None significant |
| 0 | Python Package Skeleton | ✅ COMPLETE | 12 | ~90% | `graph/__init__.py` empty |
| 1 | Shared Schemas and Evidence Model | ✅ COMPLETE | 19 | 86% | None |
| 2 | Local Graph Store and Repository Registry | ✅ COMPLETE | 17 | 80% | None |
| 3 | Repository Indexing MVP | ✅ COMPLETE | 48 | 65% | `graph/__init__.py` unused namespace |
| 4 | MCP Server Core | ✅ COMPLETE | 18 | 82% | Sub-resource file layout; prompt `.md` templates |
| 5 | Language Backend Expansion | ⚠️ PARTIAL | 30+ | 65% | TypeScript/C++/Java use Python regex fallbacks |
| 6 | SARIF and Static Analysis Layer | ✅ COMPLETE | 19 | 80% | Full SARIF JSON Schema not used for validation |
| 7 | Cross-Language Interface Plugin System | ⚠️ PARTIAL | 18 | 54% | Plugin sub-module decomposition; backlog stubs only |
| 8 | Repository Query and Repo-QA MVP | ⚠️ PARTIAL | 14 | 74% | LLM synthesis is stub |
| 9 | Fault Localisation | ⚠️ PARTIAL | 21 | 81% | Memory stub; LLM reasoning chains are heuristic |
| 10 | Evaluation Harness Baseline | ⚠️ PARTIAL | 19 | 65% | T1–T4 runners use fixture data only |
| 11 | Patch Review and Risk Gates | ⚠️ PARTIAL | 20 | 73% | Four-agent audit and vulnerability prior are stubs |
| 12 | Static Analysis Alert Repair | ⚠️ PARTIAL | 17 | 65% | Patch generator is a null stub |
| 13 | Bug-Resolve Workflow | ✅ COMPLETE | 17 | 87% | Patch generation uses null LLM stub |
| 14 | Implementation-Check Workflow | ⚠️ PARTIAL | 13 | 76% | Dynamic verdict stub; no PDF/HTML ingestion |
| 15 | Cross-Language Blast Radius | ⚠️ PARTIAL | 12 | 83% | Template instantiation stub; ABI edges incomplete |
| 16 | Dynamic Trace Augmentation | ⚠️ PARTIAL | 20 | 81% | JS/TS and C/C++ adapters raise NotImplementedError |
| 17 | Trajectory Memory and Experience Replay | ⚠️ PARTIAL | 16 | 83% | Agent-HER relabelling is NullRelabeller; in-memory store only |
| 18 | Full Evaluation, Calibration, and Release Gates | ⚠️ PARTIAL | 11 | 82% | T3/T4 use fixtures; no live benchmark execution |
| 19 | Operational Hardening and Distribution | ⚠️ PARTIAL | 12+ | 82% | Packaging not finalized; some hardening paths are stubs |

---

## 4. Critical Missing Items

The following items are the most impactful gaps for production readiness:

### High Priority (core functionality)

1. **LLM inference integration** (Phases 8, 9, 11, 12, 13, 14, 16, 17): Every phase that requires an actual LLM call has a `Null*` or placeholder implementation. The `NullPatchGenerator`, `null_summarizer`, `NullHindsightRelabeller`, QA synthesis stub, and reasoning chain stubs must be replaced with real LLM API calls (e.g., via an Anthropic/OpenAI client) before the system can produce real repairs, summaries, or relabellings. This is the single largest gap across the project.

2. **TypeScript backend — ts-morph/madge** (Phase 5): The TypeScript backend uses Python regex instead of ts-morph (accurate AST-level symbol/import/call analysis). For production-quality TypeScript graph facts, ts-morph adapter must be implemented via `asyncio.create_subprocess_exec` calling a Node.js script.

3. **C/C++ backend — libclang/clangd** (Phase 5): The C/C++ backend uses Python regex. libclang Python bindings or clangd LSP must be integrated for ABI-accurate function/type graph facts — especially important for Phase 15 ABI impact analysis.

4. **T3/T4 benchmark runners — live data** (Phase 18): The runners use pre-baked fixture data. Real calibration and release gating require connection to SWE-PolyBench/Defects4C/CodeSpecBench benchmark repositories.

### Medium Priority (fidelity gaps)

5. **SARIF v2.1.0 JSON Schema validation** (Phase 6): `sarif/parser.py` validates against a minimal inline schema dict rather than the full official SARIF v2.1.0 JSON Schema at `schemas/sarif-schema-2.1.0.json`. Strict schema-based validation should be enabled.

6. **Agent-HER hindsight relabelling** (Phase 17): `NullHindsightRelabeller` always promotes the outcome trivially. Real Agent-HER requires an LLM to relabel failed trajectories with alternative subgoals.

7. **Plugin sub-module decomposition** (Phase 7): HTTP-REST, WebSocket, and omniORB-IDL plugins each have one file instead of the designed sub-module split (e.g., `fastapi_detector.py`, `flask_detector.py`, `server_detector.py`, `idl_parser.py`). Framework-specific detection is basic regex in the plugin file.

8. **Memory persistence** (Phase 17): `MemoryStore` is an in-memory dict. For persistence across sessions, it should be backed by the Phase 2 SQLite store.

9. **`graph/__init__.py`** (Phase 3): Empty placeholder module. Should either be removed or populated with re-exports from `storage/graph_queries.py`.

### Lower Priority (hardening)

10. **Telemetry module stubs** (Phase 0): `telemetry/__init__.py` exports nothing; background flush and telemetry aggregation features referenced in Phase H0 docs are not implemented.

11. **Packaging and release automation** (Phase 19): `pyproject.toml` and uv configuration exist but GitHub Actions release workflow, wheel publishing, and version tagging automation are not finalized.

12. **C/C++ template instantiation impact** (Phase 15): `blast_radius/` notes template instantiation as a stub when backends don't provide template edge types.

---

## 5. Implementation Depth Assessment

### Modules with Strong Real Implementations (>80% real functions)

| Module | %Real | Depth Notes |
|---|---|---|
| `cli/` | 100% | Full Typer app with Rich tables, all sub-commands wired |
| `config.py` | 100% | Multi-layer TOML/JSON/env config, field validators, redaction |
| `schemas/` | 86% | Full Pydantic v2 models, `canonical_dumps`, all enum types |
| `workflows/` | 87% | Complete 10-stage bug-resolve state machine |
| `blast_radius/` | 83% | Real NetworkX traversal, 8 impact groups, cross-repo |
| `memory/` | 83% | Real write-path validation, retrieval, eviction; in-memory store |
| `hardening/` | 82% | Real file watcher, git hooks, graph chunker, drift checks |
| `release/` | 82% | Real release gate evaluator, adversarial checks, calibration |
| `mcp_server/` | 82% | Real FastMCP server, task manager, subscription manager |
| `sarif/` | 80% | Real SARIF parser, normalizer, binding, four adapters |
| `storage/` | 80% | Real SQLModel/NetworkX/aiosqlite with WAL pragmas |
| `fl/` | 81% | Real multi-signal ranking pipeline, vector cache |
| `traces/` | 81% | Real Python sys.settrace adapter, scope filter, artefact store |

### Modules with Significant Stub Content (50–75% real functions)

| Module | %Real | Primary Stubs |
|---|---|---|
| `indexing/` | 59% | TS/C++/Java backends use Python regex fallbacks; LSP lifecycle stubs |
| `plugins/` | 54% | Plugin backlog all `NotImplementedError`; plugin sub-modules collapsed |
| `evaluation/` | 65% | T1–T4 runners use fixture data; some oracle paths are stubs |
| `sast_repair/` | 65% | `NullPatchGenerator` — no LLM patch generation |
| `qa/` | 74% | `synthesis.py` LLM call is a stub |
| `patch_review/` | 73% | Four-agent audit is mock; vulnerability prior is stub |
| `impl_check/` | 76% | Dynamic verdict stage is stub |

### Modules That Are Essentially Stubs

| Module | Notes |
|---|---|
| `graph/__init__.py` | 3-line empty placeholder |
| `telemetry/__init__.py` | Empty `__all__` list |

---

*Report generated by analysing 360 source files (Python AST analysis), 112 test files, and 21 phase design documents.*
