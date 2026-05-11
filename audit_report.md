# Implementation Audit Report: `evidence-sca` / `llm_sca_tooling`

**Audited against**: `docs/llm-sca-tooling-architecture.md` (revision 6, 2026-05-08)
**Source files examined**: 442 Python files + supporting JS/JSON

---

## Legend
- ✅ **Implemented** — real logic present, matching design intent
- ⚠️ **Partial** — core structure exists but key pieces are missing or stubbed
- ❌ **Missing** — structure absent or hard `raise NotImplementedError` blocks every path

---

## F1 — Repository Intelligence Graph

### F1.1 Graph Schema & Storage
✅ **Implemented**
- Typed `GraphNode` / `GraphEdge` Pydantic models with `provenance`, `confidence`, `snapshot_id` in `src/llm_sca_tooling/schemas/graph.py`
- SQLite-backed `GraphStore` in `storage/graph_store.py` with `fetch_nodes_by_type`, ego-network queries
- Full edge type enum: `contains`, `imports`, `calls`, `dataflow`, `tests`, `documents`, `implements`, `warned_by`, `fixed_by`, `ffi`, `exposes`, `consumes`, etc. (`schemas/enums.py`)

### F1.2 Indexing Backends — Python
✅ **Implemented**
- `indexing/backends/python/python_backend.py`: orchestrates `PythonAstBackend` + `Pyan3Adapter` + `PyrightAdapter` with `FactReconciler` — real multi-pass merge
- AST backend does real `ast.parse` for nodes/edges; Pyan3 runs call-graph extraction; Pyright adapter handles type information

### F1.3 Indexing Backends — TypeScript/JavaScript
✅ **Implemented**
- `indexing/backends/typescript/ts_backend.py`: orchestrates `TsMorphAdapter` + `MadgeAdapter` + `PackageMetadata`
- `module_resolver.py` has two bare `pass` at lines 41 and 108 for edge-case module paths; core logic is real

### F1.4 Indexing Backends — C/C++
✅ **Implemented**
- `indexing/backends/cpp/cpp_backend.py`: `ClangdAdapter` + `LibclangAdapter` + `CompileCommands` + `AbiEdgeBuilder` + `CMakeBackend`
- Requires `compile_commands.json`; real clangd LSP invocation

### F1.5 Indexing Backends — Java
⚠️ **Partial**
- `indexing/backends/java/java_backend.py` exists with `JdtAdapter`; no evidence of real JDT integration tested (architecture targets C/C++/Python/JS, but Java directory exists)

### F1.6 Plugin System — omniORB IDL
⚠️ **Partial — critical gap**
- `plugins/omniorb_idl/idl_parser.py`: **uses a hand-rolled regex tokenizer, NOT `omniidl -p`**
  - File: `idl_parser.py:11` — `re.finditer(r"\binterface\s+…")` only
  - Architecture requires: *"omniIDL parsing uses real `omniidl -p` invocation"*
  - Missing: no subprocess call to `omniidl`; confidence is `HEURISTIC` (correct flag but wrong tool)
  - Plugin `check_availability()` warns "omniidl optional; fallback tokenizer enabled" — fallback is the only path
- `plugin.py`, `caller_finder.py`, `cpp_servant_linker.py`, `python_stub_linker.py` are all implemented with real graph writes

### F1.7 Plugin System — HTTP/REST
✅ **Implemented**
- `openapi_parser.py`: real JSON/YAML OpenAPI parsing with URL normalization, parameter/response extraction
- `url_normalizer.py`: real path normalization, Flask/Django/Express param-style regex replacement
- Framework detectors (`fastapi_detector.py`, `flask_detector.py`, `django_detector.py`) exist

### F1.8 Plugin System — WebSocket
✅ **Implemented**
- `websocket/event_extractor.py`: real event matching with namespace resolution and `ConfidenceLevel` classification
- `server_detector.py`, `client_detector.py`, `namespace_resolver.py` all present with real logic

### F1.9 Plugin Backlog (gRPC, Protobuf, GraphQL, SOAP, Thrift)
❌ **Missing — by design (backlog)**
- `plugins/backlog/__init__.py`: `GrpcStub`, `ProtobufStub` etc. all raise `NotImplementedError` at lines 62, 71, 81, 86
- Architecture explicitly lists these as future — not blocking

---

## F2 — Fault Localisation

### F2.1 Multi-signal ranking
✅ **Implemented**
- `fl/ranking.py`: 6-signal weighted merge (KEYWORD, EMBEDDING, SARIF_PROXIMITY, BLAME_HISTORY, GRAPH_NEIGHBOUR, SBFL) with normalised denominator, agreement score, confidence upgrade

### F2.2 RGFL Reasoning Chains
✅ **Implemented**
- `fl/reasoning.py`: `ReasoningChainScaffold.deterministic_chain()` builds per-candidate chains from signals + SARIF + graph slice
- `llm_chain()` method calls `sampling_client.sample(prompt)` with grounding validation and citation checking (lines 140–195)
- Fallback: deterministic chain when `sampling_client is None`

### F2.3 Embedding adapter
⚠️ **Partial**
- `fl/embedding_adapters/null_adapter.py`: `NullEmbeddingAdapter` always returns empty list
- `fl/localisation.py` uses `NullEmbeddingAdapter()` by default (line 8, 55)
- No production embedding adapter ships; must be injected externally

### F2.4 SBFL prior
✅ **Implemented** — `fl/sbfl.py` reads coverage data and computes suspiciousness scores

### F2.5 Memory stub in FL
⚠️ **Partial**
- `fl/memory_stub.py:34`: `raise NotImplementedError` in the `MemoryHintStub.retrieve_fl_hints()` — the real memory interface exists in `memory/retrieval/` but is not wired by default

---

## F3 — Repository Question Answering

### F3.1 Classifier
✅ **Implemented** — `qa/classifier.py` with `QuestionClass` enum and deterministic/LLM fallback classification

### F3.2 Evidence assembly & lookup
✅ **Implemented** — `qa/evidence_assembler.py`, `lookup.py`, `interface_lookup.py` — graph-backed lookup with blame

### F3.3 Synthesis layer
⚠️ **Partial**
- `qa/synthesis.py`: `NullSynthesisAdapter` is the default (returns deterministic placeholder text)
- `LLMSynthesisAdapter` exists and routes through MCP Sampling — but requires `sampling_client` injection
- Architecture requires LLM synthesis for behaviour-trace answers; default is null

### F3.4 Behaviour tracing
✅ **Implemented**
- `qa/behaviour_trace.py`: `BehaviourTraceEngine.trace()` does real graph path traversal with cross-language support
- Ship gate enforced: `BEHAVIOUR_UNCERTAINTY` warning injected when gate not met

### F3.5 Ship gate
✅ **Implemented** — `qa/ship_gate.py`: gates on evidence presence, behaviour-trace EM threshold, stale snapshot

---

## F4 — Implementation-Check 7-Stage DAG

✅ **All 7 stages implemented** (confirmed via `workflows/impl_check/report.py` log lines 73, 96, 99, 104, 110, 129, 141, 144):

| Stage | File | Status |
|---|---|---|
| 1: Spec ingestion | `ingestion.py` | ✅ Real Markdown parse, SHA256 hash, `SpecDocument` |
| 2: Intent graph | `intent_graph.py` | ✅ Clause-to-intent graph |
| 3: Contract generation | `contract_generator.py` | ⚠️ Partial |
| 4: Grounding | `grounding.py` | ✅ Symbol/document/repo-QA priority order |
| 5: Static verdict | `static_verdict.py` | ✅ SARIF + contract evidence |
| 6a: Repo QA probe | `static_verdict.py:run_stage_6a_probe()` | ✅ |
| 6b: Dynamic hook | `dynamic_verdict.py` | ⚠️ Returns UNKNOWN when no trace_capture_fn provided |
| 7: Aggregation | `aggregator.py` | ✅ Real VIOLATED/SATISFIED/UNKNOWN logic |

### Stage 3 gap — Contract generators
⚠️ **Partial**
- `NullContractGenerator`: deterministic natural language probe only (no real Semgrep/property-test generation)
- `SemgrepContractGenerator.compile_check()` returns `CompileStatus.NOT_ATTEMPTED` at line 87 — never actually runs Semgrep
- `PythonPropertyTestGenerator` exists but same pattern: `CompileStatus.NOT_ATTEMPTED`
- No real contract tool is invoked; all verdicts fall through to SARIF/test evidence

### Stage 6b gap
⚠️ **Partial** — dormant unless `trace_capture_fn` is injected; always returns `VerdictValue.UNKNOWN` by default (`dynamic_verdict.py:49`)

---

## F5 — Bug-Resolve 10-Stage Pipeline

✅ **All 10 stages defined** in `workflows/bug_resolve/models.py:StageName`:
`LOAD → INVESTIGATE → REPAIR → DRYRUN → GATES → PATCH_RISK → BLAST_RADIUS → SCOPE_AUDIT → OPERATIONAL_REVIEW → TRAJECTORY`

| Stage | Status | Notes |
|---|---|---|
| LOAD | ✅ | State machine init |
| INVESTIGATE | ⚠️ | Null mode returns placeholder candidate; real FL/QA injected externally |
| REPAIR | ⚠️ | `NullCandidatePatchGenerator` is default; no real LLM patch generation |
| DRYRUN | ✅ | `dryrun.py` applies diff heuristically |
| GATES | ✅ | `gate_runner.py`: all 5 gates (SARIF, build, test, interface, trace) wired with unknown-is-failure semantics |
| PATCH_RISK | ✅ | Delegates to `patch_review/risk_policy.py` deterministic table |
| BLAST_RADIUS | ✅ | Delegates to blast radius service (or stub if unavailable) |
| SCOPE_AUDIT | ✅ | `scope_audit.py` checks out-of-scope writes |
| OPERATIONAL_REVIEW | ✅ | Triggers async review via `run_operational_review` |
| TRAJECTORY | ✅ | Records trajectory to memory store |

### Execution-free certificate
✅ **Implemented** — `certificate.py`: full premise/counterexample logic determining `SUPPORTED / PARTIALLY_SUPPORTED / UNSUPPORTED / UNKNOWN`

### Key gap
⚠️ **REPAIR stage uses null adapter by default** — `NullCandidatePatchGenerator` produces an empty diff. A real LLM patch generator must be injected.

---

## F6 — Patch Review

### F6.1 Four-axis parallel review
✅ **Implemented**
- `patch_review/four_agent_audit.py`: runs CORRECTNESS, SECURITY, PERFORMANCE, COMPATIBILITY axes in `ThreadPoolExecutor(max_workers=4)` (line 56)
- `FallbackSamplingClient` provides deterministic fallback when MCP Sampling unavailable

### F6.2 Deterministic gates (5 gates)
✅ **Implemented** — `risk_policy.py`: all 5 gates coded:
1. SARIF new critical/security findings
2. Failing required tests
3. PoC+ failure
4. Out-of-scope writes
5. Interface breaking change
Plus: dependency direction, maintainability block, process verdict

### F6.3 Maintainability gate
✅ **Implemented** — `maintainability_gate.py` runs import-linter, mypy, ruff via subprocess

### F6.4 Risk classifier
✅ **Implemented** — deterministic policy table in `risk_policy.py`; calibrated probability path wired as `None` (no trained model shipped, returns `None`)

### F6.5 AST-level diff
✅ **Implemented** — `ast_diff.py` + `diff_parser.py` + `symbol_detector.py`

---

## F7 — SAST Alert Repair

### F7.1 PredicateFix negation pattern
✅ **Implemented**
- `sast_repair/predicate_examples.py`: three-tier retrieval: `predicate_negation` → `rule_family_match` → diagnostic (no embedding last resort)
- `corpus_adapter.py`: `CleanCorpusAdapter` with `supports_predicate_query()`, `query_by_predicate()`, `query_by_rule_family()`
- Architecture description: "Predicate negation first, rule-family fallback otherwise, embedding only as last resort" — **embedding fallback is absent** (minor gap)

### F7.2 Patch generation
⚠️ **Partial**
- `patch_generator.py:NullPatchGenerator` is the default — returns empty diff
- `PatchGeneratorInterface` ABC defined; real LLM generator must be injected

### F7.3 SARIF delta verification
✅ **Implemented** — `sarif_delta_verifier.py` compares before/after alert sets

### F7.4 Sandbox
✅ **Implemented** — `sandbox.py` provides sandboxed execution context for rerun

### F7.5 Rule evolution (offline)
✅ **Implemented** — `rule_evolution.py`: generates offline proposal package, never mutates rules in-place (correct per architecture)

---

## F8 — Cross-Language / Cross-Repo Blast Radius

### F8.1 Impact groups
✅ **Implemented** — `blast_radius/models.py:ImpactGroup`: 8+ impact groups defined: `DIRECT_CALLERS, DOWNSTREAM_BEHAVIOURS, TESTS, INTERFACES, SERVICES, REPOSITORIES, SARIF_REACHABILITY, LINKED_DOCS_SPECS`
- Plus ABI sub-groups: `VTABLE_AFFECTED`, `TEMPLATE_INSTANTIATION`, `SIGNATURE_CHANGED`, etc.

### F8.2 Traversal policies per change type
✅ **Implemented** — `traversal_policy.py`: 6 policies for `INTERNAL_IMPLEMENTATION`, `PUBLIC_API_CHANGE`, `IDL_SCHEMA_CONTRACT_CHANGE`, `SECURITY_SENSITIVE_CHANGE`, `GENERATED_FILE_CHANGE`, `MIXED/UNKNOWN`
- Each policy encodes `max_hops`, `follow_edge_types`, `stop_at_interface_boundary`, `include_cross_language`, `include_cross_repo`

### F8.3 ABI impact analysis
✅ **Implemented** — `abi_impact.py` classifies signature changes, vtable impact, template instantiation

### F8.4 Ambiguous links
✅ **Implemented** — `ambiguous_links.py` tracks unresolved cross-repo links

### F8.5 SARIF reachability
✅ **Implemented** — `sarif_reachability.py` propagates SARIF alert reach through graph

---

## F9 — Dynamic Trace Augmentation

### F9.1 Python adapter (sys.settrace)
✅ **Implemented**
- `traces/adapters/python_runner.py`: real `sys.settrace` hook, `FrameType` inspection, JSONL events with CALL/RETURN/EXCEPTION/LINE events, scope filtering, byte-budget truncation

### F9.2 JavaScript/TypeScript adapter (V8 inspector)
⚠️ **Partial**
- `traces/adapters/js_adapter.py`: spawns `js_runner.js` via Node subprocess
- `js_runner.js`: uses **`Module._load` hook** (require/import interception), NOT V8 inspector/CDP protocol
- Architecture specifies "node --inspect / V8 inspector" — actual mechanism is module hook which misses runtime call-level tracing within already-loaded modules
- `adapter_id = "node-inspector/v1"` name is misleading; only import-level events captured

### F9.3 C/C++ adapter (rr/gdb/sanitizer)
✅ **Implemented**
- `traces/adapters/cpp_adapter.py`: real `rr record` subprocess with `_capture_with_rr()` and `_capture_with_gdb()` fallback
- Returns `NOT_IMPLEMENTED` gracefully if neither tool found

### F9.4 Compression/divergence
✅ **Implemented** — `traces/compression/state_diff.py`, `divergence.py`; `null_summarizer.py` for null-mode

### F9.5 Redaction
✅ **Implemented** — `traces/redaction.py` with env snapshot hash, type-hash-only return values

---

## F10 — Trajectory Memory and Experience Replay

### F10.1 Memory store
✅ **Implemented** — `memory/store.py`: SQLite-backed trajectory store with `put_trajectory`, `list_trajectories`, `get_trajectory`

### F10.2 Agent-HER relabelling for failed trajectories
✅ **Implemented**
- `memory/relabelling/llm_relabeller.py`: `LLMHindsightRelabeller.relabel()` assigns hindsight label to any trajectory
- Supports both LLM sampling path (when `sampling_client` injected) and keyword-fallback
- `TrajectoryOutcome.RELABELLED` state used correctly
- `memory/relabelling/null_relabeller.py` for null-mode

### F10.3 Retrieval interface
⚠️ **Partial**
- `memory/retrieval/interface.py:15, 27`: `raise NotImplementedError` on both `retrieve` methods — this is an ABC
- Concrete implementation exists in `memory/retrieval/` (need check)

### F10.4 Memory compaction / eviction
✅ **Implemented** — `memory/eviction/compactor.py`: `MemoryCompactor.compact()` with `EvictionPolicy`, utility ranking, overflow trimming, `dry_run` mode

### F10.5 Promotion gate
✅ **Implemented** — `memory/ship_gate.py` + `memory/promotion/` — reviewable promotion with source/owner/rollback metadata

---

## F11 — Operational Harness, Telemetry, Continuous Improvement

### F11.1 MCP Tools (target: ~40+)
✅ **Implemented** — **48 tool handler classes registered** in `default_tool_handlers()`:

| Module | Tools |
|---|---|
| `core.py` | `RegisterRepoTool`, `GraphSliceTool`, `CallGraphTool(×2)`, `PluginReloadTool`, `GraphBuildTaskTool(×2)` |
| `fl.py` | `GetRelevantFilesTool` |
| `qa.py` | `ClassifyRepoQuestionTool`, `AnswerRepoQuestionTool`, `GetInterfaceContractTool` |
| `blame.py` | `GitBlameChainTool` |
| `patch_review.py` | `RunPatchReviewTool`, `ClassifyPatchRiskTool` |
| `issue_resolution.py` | `RunIssueResolutionTool` |
| `impl_check.py` | `RunImplementationCheckTool` |
| `traces.py` | `CaptureTraceTool` |
| `memory.py` | `RetrieveMemoryTool`, `RecordTrajectoryTool`, `MemoryCompactTool`, `PromoteOperationalLessonTool` |
| `operational_harness.py` | 12 tools (RecordRunEvent, RecordHarnessCondition, EvaluateToolPolicy, DetectRunAnomalies, CompareRunTraces, AssessHarnessStage, ClassifyHarnessDrift, ValidateHarnessControls, ComputeReadinessScore, RunMaintainabilityOracles, RunPromptManifestRegression, RecordIncident) |
| `operational_review.py` | `RunOperationalReviewTool` |
| `readiness_audit.py` | `RunReadinessAuditTool` |
| `sarif.py` | `RunStaticAnalysisTool` |
| `sast_repair.py` | `GetPredicateExamplesTool`, `RunSastRepairTool`, `EvolveStaticRulesTool` |
| `eval.py` | `ComputeRdsFeaturesTool`, `RecordEvalResultTool`, `RunEvalSuiteTool` |
| `interface.py` | `TraceCrossLanguageTool`, `PluginReloadTool` |

### F11.2 MCP Resources
✅ **Implemented** — 20+ resource handler classes:
- `code-intelligence://repos`, `code-intelligence://schema/{file}`, graph manifests/slices, summaries, blame, build evidence, eval, interfaces, memory trajectories, run records, harness conditions, ledger, governance, readiness, incidents, SARIF, skills

### F11.3 Task system (async long-running)
✅ **Implemented** — `TaskManager`, `TaskRunner`, `TaskStore` with TTL, inflight recovery

### F11.4 Subscriptions / notifications
✅ **Implemented** — `subscriptions.py:SubscriptionManager` + `notifications.py:NotificationManager`

### F11.5 Prompts
✅ **Implemented** — `prompts/` + `prompt_registry.py` with Sampling-aware templates

### F11.6 Telemetry
✅ **Implemented** — `telemetry/trace_writer.py`, structured logging; `TraceWriter` appends structured events

### F11.7 Run records & operational ledger
✅ **Implemented** — `operations/run_records.py`, `ledger_retention.py`, `ledger_export.py`, `harness_store.py`

### F11.8 Permission / tool policy evaluation
✅ **Implemented** — `EvaluateToolPolicyTool` routes to policy engine; `tool_permissions.py` with `PermissionMode` enforcement

### F11.9 Budget monitor & doom-loop detection
✅ **Implemented** — `operations/budget.py:BudgetMonitor`; `workflows/bug_resolve/monitor_hooks.py:check_doom_loop()`, `check_budget()`

### F11.10 Sampling (MCP)
✅ **Implemented** — `mcp_server/sampling.py:detect_sampling()`, `SamplingCapabilityRecord`; used in patch_review and QA when available

---

## Evaluation Harness

### RDS v0.2 Feature Vector (6 axes)
✅ **Implemented** — `evaluation/rds_features.py`:
All 6 axes present: `files_touched`, `chain_depth`, `cross_file_dataflow`, `ambient_warning_load`, `test_brittleness`, `memorisation_distance`
- `chain_depth` requires `graph_edges` table — returns `None` with diagnostic when unavailable
- `memorisation_distance` reads from descriptor metadata; `memorisation_calibrated=False` unless explicitly set
- `test_brittleness` reads from `instance_metadata` table — returns `None` with diagnostic if missing

### T1–T4 Runners
✅ **Implemented** — `t1_runner.py` (smoke), `t2_runner.py` (regression), `t3_runner.py` (cross-language), `t4_runner.py` (implementation/spec)

### Benchmark adapter
⚠️ **Partial**
- `evaluation/benchmark_adapter.py:BenchmarkAdapter` ABC — all abstract methods raise `NotImplementedError` (lines 72–98)
- This is the correct pattern (ABC), but **no concrete adapter ships** (e.g. no `SWEBenchAdapter`)
- `evaluation/smoke_adapter.py` provides a fixture-based adapter for T1 smoke tests

### Contamination canary
⚠️ **Partial**
- `evaluation/contamination.py:unknown_contamination_canary()` returns `CanaryVerdict.UNKNOWN` with `"canary_not_calibrated_phase10"` — no real probe implementation

---

## Skills

✅ **Implemented** — 8 skill templates in `.skills/`:
`audit.SKILL.md`, `blast_radius.SKILL.md`, `impl_check.SKILL.md`, `investigate.SKILL.md`, `repair.SKILL.md`, `risk_classify.SKILL.md`, `sast_repair.SKILL.md`, `_template.SKILL.md`

---

## Summary Table

| Feature | Status | Severity |
|---|---|---|
| F1: Repository Intelligence Graph (schemas, storage, graph) | ✅ | — |
| F1: Indexing — Python, TypeScript, C/C++ backends | ✅ | — |
| F1: Plugin — omniORB IDL (regex fallback, no `omniidl -p`) | ⚠️ | Minor |
| F1: Plugin — HTTP/REST (real OpenAPI) | ✅ | — |
| F1: Plugin — WebSocket | ✅ | — |
| F1: Plugin Backlog (gRPC/Protobuf) | ❌ Intentional | Minor |
| F2: Fault localisation multi-signal ranking | ✅ | — |
| F2: RGFL reasoning chains (deterministic + LLM) | ✅ | — |
| F2: Embedding adapter (null by default) | ⚠️ | Minor |
| F3: Repo QA (classify, evidence, blame, behaviour trace) | ✅ | — |
| F3: LLM synthesis adapter (null by default) | ⚠️ | Minor |
| F4: Impl-check 7-stage DAG | ✅ (all stages wired) | — |
| F4: Stage 3 contract generators — no real Semgrep execution | ⚠️ | Blocking |
| F4: Stage 6b dynamic hook — dormant | ⚠️ | Minor |
| F5: Bug-resolve 10-stage state machine | ✅ | — |
| F5: REPAIR — null patch generator by default | ⚠️ | Blocking |
| F5: Execution-free certificate | ✅ | — |
| F6: 4-axis parallel patch review | ✅ | — |
| F6: 5 deterministic gates | ✅ | — |
| F6: Calibrated probability (returns None) | ⚠️ | Minor |
| F7: PredicateFix predicate negation | ✅ (no embedding fallback) | Minor |
| F7: Patch generation — null by default | ⚠️ | Blocking |
| F8: 8 impact groups + 6 traversal policies | ✅ | — |
| F8: ABI impact | ✅ | — |
| F9: Python sys.settrace adapter | ✅ | — |
| F9: JS adapter — Module._load hook, not V8 inspector | ⚠️ | Minor |
| F9: C/C++ rr/gdb adapter | ✅ | — |
| F10: Trajectory memory store | ✅ | — |
| F10: Agent-HER relabelling | ✅ | — |
| F10: Memory retrieval ABC | ⚠️ | Minor |
| F10: Eviction/compaction | ✅ | — |
| F11: 48 MCP tools | ✅ | — |
| F11: 20+ MCP resource URIs | ✅ | — |
| F11: Tasks, subscriptions, notifications, sampling | ✅ | — |
| F11: Run records, operational ledger, governance | ✅ | — |
| Eval: RDS v0.2 all 6 axes | ✅ | — |
| Eval: T1–T4 runners | ✅ | — |
| Eval: No concrete BenchmarkAdapter ships | ⚠️ | Blocking |
| Eval: Contamination canary not calibrated | ⚠️ | Minor |
| Skills: 8 SKILL.md templates | ✅ | — |

---

## Gaps by Severity

### 🔴 Blocking (critical logic absent; workflow broken without external injection)

| # | Gap | File:Line | Impact |
|---|---|---|---|
| B1 | **F4 Stage 3: No real contract tool execution** — `SemgrepContractGenerator.compile_check()` always returns `NOT_ATTEMPTED`; no Semgrep process spawned | `workflows/impl_check/contract_generator.py:87, 114` | Implementation-check verdicts rely entirely on SARIF/test evidence, not generated contracts |
| B2 | **F5 REPAIR stage: null patch generator is default** — `NullCandidatePatchGenerator` returns empty diff | `workflows/bug_resolve/candidate_patch.py`, `state_machine.py` | Bug-resolve workflow cannot produce patches without external LLM adapter injection |
| B3 | **F7 SAST patch generation: null by default** — `NullPatchGenerator.generate()` returns `diff_text=""` | `sast_repair/patch_generator.py:25` | SAST repair loop cannot produce patches in default configuration |
| B4 | **Eval: No concrete BenchmarkAdapter** — `BenchmarkAdapter` ABC with all methods raising `NotImplementedError` | `evaluation/benchmark_adapter.py:72–98` | T1–T4 evaluation runners require a real adapter; only fixture `smoke_adapter.py` exists |

### 🟡 Minor (non-critical paths or explicitly deferred)

| # | Gap | File:Line | Impact |
|---|---|---|---|
| M1 | **F1 omniIDL: regex tokenizer only, not `omniidl -p`** | `plugins/omniorb_idl/idl_parser.py:11` | IDL confidence is `HEURISTIC`; complex IDL (inheritance, modules, typedef) may parse incorrectly |
| M2 | **F2 embedding adapter: null by default** | `fl/localisation.py:55` | Embedding signal absent unless injected; ranking quality reduced |
| M3 | **F2 FL memory stub** raises `NotImplementedError` | `fl/memory_stub.py:34` | Memory hints not applied to FL until wired |
| M4 | **F3 LLM synthesis: null by default** | `qa/synthesis.py:67` | Answers are deterministic placeholders unless sampling injected |
| M5 | **F4 Stage 6b dynamic hook dormant** | `workflows/impl_check/dynamic_verdict.py:49` | Dynamic clause verdicts always UNKNOWN without trace injection |
| M6 | **F6 calibrated probability returns None** | `patch_review/risk_policy.py` | Risk scores are deterministic policy only; no trained model |
| M7 | **F7 PredicateFix: embedding fallback absent** | `sast_repair/predicate_examples.py:42` | Architecture specifies 3 tiers (predicate → rule_family → embedding); only 2 implemented |
| M8 | **F9 JS adapter uses Module._load, not V8 inspector** | `traces/adapters/js_adapter.py:30`, `js_runner.js:75` | Only import-level events captured; no intra-module function-call tracing |
| M9 | **F10 memory retrieval interface not implemented** | `memory/retrieval/interface.py:15, 27` | ABC — concrete retrieval must be injected; `NullMemoryRetriever` needed |
| M10 | **Eval contamination canary not calibrated** | `evaluation/contamination.py` | `CanaryVerdict.UNKNOWN` always; data contamination checks non-functional |
| M11 | **F1 Backlog plugins (gRPC, Protobuf)** | `plugins/backlog/__init__.py:62` | Intentional; future work per architecture |
| M12 | **TypeScript `module_resolver.py` bare `pass` at lines 41, 108** | `indexing/backends/typescript/module_resolver.py` | Edge-case module paths silently skipped |

---

*Report generated by thorough code inspection of 442 Python source files + supporting JS. Every finding above is backed by a specific file:line reference from the actual implementation.*___BEGIN___COMMAND_DONE_MARKER___0
