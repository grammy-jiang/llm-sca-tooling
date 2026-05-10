# Research Method Implementation Matrix

This matrix tracks the implementation state of the methods summarized in
`docs/llm-based-static-code-analysis-research-report.md` and projected into
`docs/llm-sca-tooling-architecture.md`.

Network access is denied by repository policy, so this audit is based primarily
on the local research report and architecture document rather than fresh
retrieval of the original papers. A retry found converted-paper Markdown for a
subset of relevant papers in the external local research-pipeline workspace at
`/home/grammy-jiang/Documents/Research/static-code-analysis`; see
`docs/original-paper-fetching-limitation.md` for the inventory, limitation
record, and next-step remediation plan.

| Method / claim | Expected implementation | Current implementation evidence | Status | Remaining gap |
|---|---|---|---|---|
| FL-context / file-level localization improves repair | Rank files/symbols from graph, blame, SARIF, tests, SBFL, memory, embeddings; evaluate repair lift | `fl/localisation.py`, `get_relevant_files`, SARIF/blame hooks | Partial | Embeddings/SBFL/memory are optional or unavailable; no 15-17x-style repair-lift eval gate |
| RepoGraph / RIG polyglot graph substrate | Typed nodes and edges for contains/imports/calls/dataflow/tests/documents/interfaces/SARIF across Python, JS/TS, Java, C/C++ | `indexing/`, `plugins/`, `graph_update`, `trace_cross_language`; cache dirs excluded by scanner | Partial | Dataflow and cross-language coverage are fixture-level; graph completeness must be benchmarked per language |
| Gap 1 design-doc implementation audit | Intent parser, ontology, executable contracts, graph grounding, static/dynamic verdict, calibrated aggregation | `run_implementation_check`, clause extraction, grounding, contract generator interface, dynamic hook | Partial | Contract generators are limited/null by default; most unsupported clauses still resolve unknown; no ECE calibration bundle |
| KGACG / MIDS-Valve-style structured intent | Convert prose requirements into typed, atomic, scoped clauses and intent graph | `impl_check/clause_extractor.py`, `intent_graph.py` | Partial | Heuristic parser only; no learned ontology extraction or benchmarked parser accuracy |
| JML-Autodoc / PredicateFix executable contracts | Generate verifier/analyzer/test predicates from clauses | `contract_generator.py`, SAST predicate metadata/examples | Partial | No full CodeQL/JML/Semgrep generation pipeline for arbitrary clauses |
| Soft repo-QA for behavior tracing | Answer repo questions from graph-backed evidence with confidence and citations | `classify_repo_question`, `answer_repo_question`, QA modules | Partial | Behavior QA is useful for file location, weak for semantic behavior; no >=70% behavior benchmark gate |
| Dynamic trace augmentation | Scoped trace capture, compression, state diff, integration into impl-check/bug-resolve/review | `capture_trace`, Python adapter, state diff; FK persistence fixed for registered repos | Partial | JS/C++ adapters remain placeholders; workflow auto-invocation is limited |
| Correct-not-safe / COMPASS patch risk classifier | Classify safe/correct-but-overfit/vulnerable/vulnerability-introducing with AST/SARIF/graph/test features and calibration | `classify_patch_risk`, `run_patch_review`, deterministic features | Partial | No trained contrastive model, macro-F1/ECE report, or PVBench/PoC+ dataset adapter |
| SAST PredicateFix repair loop | SARIF alert -> predicate metadata/examples -> patch -> analyzer rerun/SARIF delta -> tests | `run_sast_repair`, predicate examples, analyzer rerun helpers | Partial | Analyzer rerun availability depends on local tools; full rule-family coverage incomplete |
| Static rule evolution | Build offline rule candidates from SARIF deltas with FP/TP promotion gate | `evolve_static_rules` now returns reviewable candidate package | Partial | Does not mutate/publish rules; needs offline benchmark proving >=10 pp FP reduction with zero TP loss |
| Blast radius / RIG impact closure | Traverse graph from changed symbols across callers, tests, interfaces, docs, SARIF, cross-repo links | `BlastRadiusService`; bug-resolve now calls service when changed symbols exist | Partial | Null repair candidates still lack changed symbols; cross-repo data depends on registered repo set |
| RDS repository difficulty score | Log six axes and correlate with benchmark outcomes | `compute_rds_features` | Partial | Gap 4 remains academic; no cross-benchmark regression validation |
| Memory / replay / Agent-HER / Evo-Memory | Store trajectories, retrieve negative examples, evict by utility, A/B gate at constant context | memory store, `retrieve_memory`, `memory_compact` | Partial | FL/repair/review do not yet use memory as a validated signal; no >=3 pp A/B gate |
| Operational harness | Append-only run ledger, policy checks, drift/readiness, incidents, promotion candidates | operational MCP tools, shared readiness scoring, real run review fallback | Partial | Operational review needs more anomaly detectors and promotion-candidate generation |
| Evaluation ladder T1-T4 | PR smoke, nightly, weekly, release calibration suites with fixed datasets | `run_eval_suite`, T1-T4 runner skeletons | Partial | Most benchmark adapters are local/smoke only; external datasets require approved data/network policy |

## Acceptance Gates

- `make verify` passes before claiming S3 production evidence.
- `run_implementation_check` must return satisfied/violated on known fixture
  specs, not only unknown.
- `capture_trace` must store artifacts without foreign-key failures and expose a
  readable run record.
- `run_issue_resolution` must use real blast-radius evidence when a candidate
  patch has graph symbols.
- `run_patch_review` and `classify_patch_risk` must label deterministic fallback
  output as uncalibrated until a measured classifier is added.
- `evolve_static_rules` must remain offline-only until promotion metrics are
  recorded.
