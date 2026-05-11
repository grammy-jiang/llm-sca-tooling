# LLM-SCA Tooling Phase 10 Implementation Plan: Evaluation Harness Baseline

> Date: 2026-05-09
> Repository name: `evidence-sca`
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 10 - Evaluation Harness Baseline
> Primary objective: establish measurement infrastructure before adding high-level repair automation — produce typed eval-run records, Harness Condition Sheets, RDS v0.2 feature vectors, T1/T2 benchmark runners, operational-quality metrics, and the private `evaluate` template that launches `run_eval_suite`.

---

## 1. Phase Summary

Phase 10 is the first evaluation-facing phase of `evidence-sca`. Phases 1-9 built the index, MCP server, language backends, SARIF layer, interface plugins, repo-QA, and fault localisation. Phase 10 adds the measurement system that makes all earlier evidence auditable as release-quality claims.

The central rule for this phase is:

```text
Quality claims must hold the model and runtime fixed and report the harness condition.
No benchmark number is accepted without a Harness Condition Sheet.
No RDS feature vector is accepted without per-instance logging.
No eval run is reproducible without a stored artefact manifest.
LLM-as-judge output cannot substitute for a deterministic eval gate.
```

Phase 10 should implement:

- Evaluation run model and typed records.
- Harness Condition Sheet model and renderer.
- Benchmark adapter interface.
- Local smoke benchmark format.
- T1 smoke runner and T2 regression runner skeleton.
- FL metrics: top-1, top-3, top-N, and FL-conditioned repair rate.
- RDS v0.2 six-axis feature computation.
- Operational-quality metrics alongside task metrics.
- Structural maintainability oracle adapter.
- AI-readiness report generator.
- Contamination canary and suite-freshness metadata.
- Flaky-test detection and exclusion metadata.
- Repeated-trial and perturbation runner skeleton.
- Prompt, manifest, and tool-description regression test adapter.
- `code-intelligence://eval/{run_id}` resource.
- `run_eval_suite`, `compute_rds_features`, and `record_eval_result` tools.
- Private `evaluate` skill template.

### Architecture Coverage

Phase 10 covers:

- Evaluation harness from the architecture (§14.3 T1-T4 benchmark ladder).
- `code-intelligence://eval/{run_id}` resource.
- `run_eval_suite` tool.
- `compute_rds_features` tool.
- `record_eval_result` tool.
- F11 operational-quality measurement integration.
- H7 evaluation-harness harness control.
- RDS v0.2 feature logging (architecture §13.4).

MCP resource in this phase:

- `code-intelligence://eval/{run_id}`

Tools in this phase:

- `run_eval_suite`
- `compute_rds_features`
- `record_eval_result`

Private skill template in this phase:

- `evaluate`

### Inherited Paper Anchors

Use these anchors in Phase 10 issues, ADRs, and evaluation reports:

- `swe-bench-live`
- `swd-bench`
- `swe-polybench`
- `defects4c`
- `codespecbench`
- `swe-bench-illusion`
- `swe-qa-pro`
- `livecoder`
- `swe-rebench-v2`
- `pvbench`

Adjacent anchors useful for harness and operational notes:

- `agenttrace`
- `aer`
- `runtime-governance`
- `tokalator`
- `workstream`
- `needle-repo`

## Technology Stack

Phase 10 establishes the evaluation harness. The primary additions are the testing and schema-validation libraries needed to drive eval suites and generate edge-case fixtures.

| Library / Tool | PyPI package | Version | Purpose in this phase |
|---|---|---|---|
| Python | — | >=3.12 | Language baseline; all async I/O via `asyncio.create_subprocess_exec` |
| uv | — | latest | Environment and dependency management |
| Pydantic v2 | `pydantic` | >=2.0 | `EvalRun`, `EvalInstanceResult`, `HarnessConditionSheet`, `RDSFeatureVector`, `OperationalQualityMetrics`, `AIReadinessReport`, `ContaminationCanaryResult`, `FreshnessRecord`, and all eval models; `extra="forbid"`, schemas via `model_json_schema()` |
| orjson | `orjson` | >=3.10 | Eval result serialisation; JSONL output for per-instance result streams; fast round-trip of `EvalRun` artefacts |
| SQLModel + Alembic | `sqlmodel`, `alembic` | >=0.0.21, >=1.13 | Eval-run and harness-condition records in the operational store; schema migrations for new eval tables |
| aiosqlite | `aiosqlite` | >=0.20 | Async SQLite driver for the eval artefact store and operational store reads |
| asyncpg | `asyncpg` | >=0.29 | Async PostgreSQL driver; used when production Postgres backend is configured |
| NetworkX | `networkx` | >=3.3 | RDS feature computation — `chain_depth` and `cross_file_dataflow` axes require graph traversal (Section 9.2) |
| FastMCP | `fastmcp` | >=2.0 | MCP server framework for `run_eval_suite`, `compute_rds_features`, and `record_eval_result` tool handlers and the `code-intelligence://eval/{run_id}` resource |
| FastAPI | `fastapi` | >=0.115 | HTTP layer for the MCP server |
| pytest | `pytest` | >=8.0 | Test runner for all evaluation harness unit, integration, and T1 smoke tests |
| pytest-asyncio | `pytest-asyncio` | >=0.23 | Async test support for eval harness; `asyncio_mode="auto"` in `pyproject.toml` |
| pytest-cov | `pytest-cov` | >=5.0 | Coverage measurement in eval runs; `evaluation/` modules target >85% |
| pytest-xdist | `pytest-xdist` | >=3.5 | Parallel test execution (`-n auto`) for large eval suites; T1 smoke instances run in parallel workers |
| tox | `tox` | >=4.0 | Multi-version matrix for reproducibility across Python versions; ensures eval infrastructure is version-stable |
| jsonschema | `jsonschema` | >=4.23 | Validates eval result payloads against Pydantic-exported JSON schemas; used in `record_eval_result` and the replay helper |
| jsf | `jsf` | >=0.11 | Generates edge-case fixture inputs for the eval harness from exported schemas; used when building new smoke fixture instances |
| import-linter | `import-linter` | >=2.1 | Architectural layering enforcement; `evaluation/` must not import from `fl/` directly — only through the Phase 9 public API |

**Integration notes:**

- `HarnessConditionWriter` is the canonical way to record harness conditions in every eval run. Import it as `from llm_sca_tooling.harness import HarnessConditionWriter`. Every eval run must call `HarnessConditionWriter.write(run_id=..., model=..., manifest_hash=..., tool_set=..., permission_profile=...)` before metrics are reported.
- `jsonschema` validates the `EvalRun` JSON payload on write (via `record_eval_result`) and on read (via the resource handler). Validation failures must be surfaced as typed errors, not swallowed.
- `jsf` is used at test-fixture generation time, not at runtime. Call it from `scripts/generate_smoke_fixtures.py` to produce new edge-case instances in `tests/evaluation/fixtures/smoke/`.
- `pytest-xdist` is enabled with `-n auto` for the T1 smoke runner test suite; individual T1 instance tests are independent and safe to parallelise.
- All async store I/O (eval artefact writes, run-event recording) uses the SQLModel async session. No synchronous blocking calls in the eval hot path.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 10 depends on:

- Phase 1 schemas:
  - run-record schema
  - harness condition schema
  - verdict and evidence models
  - operational event schema
  - AI-readiness report schema
- Phase 2 stores:
  - operational store for run records and events
  - artefact registry
  - snapshot ledger
- Phase 4 infrastructure:
  - task manager and task persistence
  - resource routing and notification hooks
  - tool-description regression harness skeleton
- Phase 9 fault-localisation output:
  - `LocalisationResult` with `ranked_candidates`, `agreement_score`, `budget_used`, `provenance`
  - FL metrics: top-1, top-3, top-N
- Phase 4A operational harness (if available):
  - `record_harness_condition`, `record_run_event`
  - harness-stage and drift-classification tooling

### Phase Outputs

Phase 10 should produce:

- `EvalRun` model and typed evaluation records.
- `HarnessConditionSheet` model and renderer.
- `BenchmarkAdapter` interface and local smoke fixture adapter.
- `RDSFeatureVector` model with six axes.
- T1 smoke runner.
- T2 regression runner skeleton.
- Repeated-trial / perturbation runner skeleton.
- FL metric computer.
- Operational-quality metric computer.
- Structural maintainability oracle adapter.
- AI-readiness report generator.
- Contamination canary metadata model.
- Flaky-test detector.
- Prompt/manifest/tool-description regression test adapter.
- Eval resource handler.
- `run_eval_suite`, `compute_rds_features`, `record_eval_result` tool handlers.
- Private `evaluate` skill template.
- Eval-run artefact writer and replay helper.
- Eval-run tests.

### Non-Goals

Do not implement these in Phase 10:

- T3 or T4 external benchmark integration (skeleton only).
- External benchmark API clients or network fetchers.
- Full trained patch-risk classifier (Phase 11).
- Bug-resolve or repair workflows (Phase 13).
- Implementation-check workflow (Phase 14).
- Dynamic trace capture (Phase 16).
- Trajectory memory (Phase 17).
- Production release gates (Phase 18).
- Calibrated LLM-as-judge verdict acceptance.

---

## 3. Recommended File Layout

Assuming package name `evidence_sca`:

```text
src/evidence_sca/
  evaluation/
    __init__.py
    models.py
    harness_condition.py
    rds_features.py
    fl_metrics.py
    operational_metrics.py
    maintainability_oracle.py
    ai_readiness.py
    benchmark_adapter.py
    smoke_adapter.py
    t1_runner.py
    t2_runner.py
    perturbation_runner.py
    flaky_detector.py
    contamination.py
    regression_adapter.py
    artefact_writer.py
    replay.py

  mcp_server/
    tools/
      eval.py
    resources/
      eval.py

  skills/
    evaluate.md

tests/
  evaluation/
    fixtures/
      smoke/
        instance_01/
          issue.json
          gold_patch.diff
          gold_suspects.json
          rds_features.json
        instance_02/
          ...
    test_eval_run_model.py
    test_harness_condition_sheet.py
    test_rds_features.py
    test_fl_metrics.py
    test_operational_metrics.py
    test_maintainability_oracle.py
    test_ai_readiness.py
    test_t1_runner.py
    test_contamination.py
    test_flaky_detector.py
    test_regression_adapter.py
    test_eval_resource.py
    test_eval_tools.py
    test_evaluate_template.py
```

---

## 4. Evaluation Run Model

### 4.1 Purpose

Every benchmark run must produce a typed `EvalRun` record that stores all dimensions needed for reproducibility, comparison, and trend analysis.

### 4.2 `EvalRun` Model

Required fields:

```text
EvalRun
  eval_run_id
  suite_id
  suite_version
  suite_median_age_days
  target_workflow
  target_tool
  model_backend
  toolset_hash
  policy_id
  permission_profile
  harness_condition_id
  start_ts
  end_ts
  status
  instance_count
  instance_results_ref
  aggregate_metrics_ref
  rds_summary_ref
  operational_metrics_ref
  contamination_canary_result
  freshness_check_ts
  artefact_manifest_ref
  run_record_id
  notes
```

Status values:

- `running`
- `completed`
- `failed`
- `cancelled`
- `partial`

### 4.3 `EvalInstanceResult` Model

Required fields:

```text
EvalInstanceResult
  instance_id
  eval_run_id
  suite_id
  issue_ref
  gold_patch_ref
  candidate_patch_ref
  fl_result_ref
  fl_top1_correct
  fl_top3_correct
  fl_topN_correct
  fl_conditioned_repair_correct
  repair_correct
  gate_results
  rds_features
  contamination_flag
  flaky_flag
  wall_ms
  token_count
  budget_events
  incident_ids
  notes
```

### 4.4 Suite ID and Versioning

Rules:

- Every suite has a stable `suite_id` and a `suite_version` that changes when instances are added, removed, or patched.
- `suite_median_age_days` must be computed and stored at run time, not imputed from suite version.
- External suites (`swe-bench-live`) must record their refresh date.
- Stale suites do not invalidate results but must flag the staleness in the report.

### 4.5 Eval Run Tests

Required tests:

- `EvalRun` round-trips through JSON.
- Missing required fields fail validation.
- `EvalInstanceResult` stores all gate results.
- `eval_run_id` is high entropy and non-predictable.
- Partial runs persist completed instances.

---

## 5. Harness Condition Sheet

### 5.1 Purpose

Every eval run, workflow execution, and release-gate report must include a compact Harness Condition Sheet so benchmark and production outcomes are comparable across models, tool sets, policies, and context strategies.

### 5.2 `HarnessConditionSheet` Model

Required fields:

```text
HarnessConditionSheet
  hcs_id
  run_id
  model_backend
  model_version
  manifest_hashes
  tool_set
  tool_set_hash
  permission_mode
  sandbox_policy
  network_policy
  verification_gates
  context_policy
  context_budget
  retry_policy
  telemetry_location
  redaction_policy
  cost_limit
  harness_stage
  harness_drift_status
  created_ts
```

### 5.3 Renderer

The renderer should produce:

- A compact single-paragraph text form for inline reports.
- A structured JSON form for machine comparison.
- A diff-friendly key-value form for trend comparison across runs.

### 5.4 Rules

Rules:

- Every eval run must attach a `HarnessConditionSheet` before metrics are reported.
- Benchmark reports without a `HarnessConditionSheet` cannot be accepted as release-gate evidence.
- `HarnessConditionSheet` comparison must detect drift in: model, manifest hash, tool set, permission mode, or verification gates.

### 5.5 Tests

Required tests:

- Sheet serializes to compact and JSON forms.
- Missing model or manifest hash fails validation.
- Two sheets can be diffed for changed fields.
- Sheet is stable under repeated rendering of same fields.

---

## 6. Benchmark Adapter Interface

### 6.1 Purpose

The adapter interface decouples the eval runner from specific suite formats, so T1 smoke fixtures, local equivalents, and future external suites share the same runner.

### 6.2 `BenchmarkAdapter` Interface

Recommended interface:

```text
BenchmarkAdapter
  suite_id
  suite_version
  list_instances() -> list[InstanceDescriptor]
  load_issue(instance_id) -> IssueRecord
  load_gold_patch(instance_id) -> GoldPatchRecord
  load_gold_suspects(instance_id) -> list[SuspectRecord]
  check_instance_availability(instance_id) -> AvailabilityStatus
  freshness_check() -> FreshnessRecord
  contamination_canary(model_id?) -> ContaminationResult
```

Recommended `InstanceDescriptor`:

```text
InstanceDescriptor
  instance_id
  suite_id
  language
  repo_id
  issue_ref
  gold_patch_ref
  gold_suspects_ref
  rds_features
  difficulty_tags
  contamination_canary_flag
  available
```

### 6.3 `LocalSmokeAdapter`

The first concrete adapter:

- Loads instances from `tests/evaluation/fixtures/smoke/`.
- Each instance is a directory with `issue.json`, `gold_patch.diff`, `gold_suspects.json`, and optional `rds_features.json`.
- No network access required.
- Supports filtering by language, tag, and RDS feature range.

### 6.4 Suite Freshness and Contamination

Rules:

- `freshness_check()` computes `suite_median_age_days` from instance commit dates.
- Contamination canary checks a known clean probe instance against the model's memorisation window.
- Canary results are advisory only in Phase 10 — they must be logged but cannot gate the run without a validated canary policy.
- `swe-bench-live` must be refreshed monthly for external-quality reporting.

### 6.5 Tests

Required tests:

- Smoke adapter loads fixture instances.
- Missing gold suspects returns graceful empty list.
- Freshness check returns median age.
- Contamination canary result is stored in eval run.

---

## 7. T1 Smoke Runner

### 7.1 Purpose

The T1 runner is the first-tier benchmark runner. It runs a small set of local smoke instances to verify basic pipeline health before investing in larger suites.

### 7.2 T1 Acceptance Criteria

T1 instances must include at least:

- One file-localisation instance (issue maps to a single file).
- One multi-file localisation instance (issue spans 2-3 files).
- One ambiguity instance (issue is underspecified or has multiple plausible locations).
- One security-sensitive instance (SARIF alert or vulnerability class).
- One maintainability instance (passing public tests is insufficient to confirm correctness).

### 7.3 Runner Algorithm

For each instance:

1. Resolve `IssueRecord` from adapter.
2. Call `compute_rds_features` and store vector.
3. Run fault localisation pipeline (Phase 9 `get_relevant_files`).
4. Store FL result and compute top-1/top-3/top-N FL metrics.
5. Record operational events: token count, wall time, budget events.
6. Store `EvalInstanceResult`.
7. After all instances: aggregate metrics, generate `HarnessConditionSheet`, write `EvalRun`.

### 7.4 Null-Mode Runner

The T1 runner must support a null mode:

- Fault localisation runs against smoke instances without calling external LLMs.
- Embedding is provided by the null adapter from Phase 9.
- LLM synthesis is provided by a null synthesiser that returns empty reasoning chains.
- All pipeline infrastructure, metric computation, and artefact writing still execute.
- Used in CI to verify harness infrastructure without LLM costs.

### 7.5 Tests

Required tests:

- T1 null-mode run completes all five required instance types.
- FL metrics are computed per instance and in aggregate.
- `EvalRun` is stored and retrievable.
- `HarnessConditionSheet` is attached.
- Null-mode output is stable under repeated runs.

---

## 8. T2 Regression Runner Skeleton

### 8.1 Purpose

The T2 skeleton defines the interface for a longer regression suite without requiring a full external benchmark in Phase 10.

### 8.2 T2 Architecture

T2 builds on T1 by adding:

- A configurable number of instances up to the full smoke library plus local equivalents.
- A retained baseline `EvalRun` for comparison.
- A regression verdict: better, equal, regressed, or inconclusive.
- A suite-freshness assertion that fails the runner if `suite_median_age_days` exceeds the configured threshold.

### 8.3 T3/T4 Stubs

T3 and T4 runners are stubs in Phase 10:

- They share the `BenchmarkAdapter` interface.
- They record a `not_implemented_until_phase_X` status.
- They do not attempt external network calls.

### 8.4 External Benchmark Adapter Notes

Rules for future external adapters:

- `swe-bench-live` must be the headline suite for external-quality resolve-rate, not SWE-bench Verified.
- `swd-bench` Functionality-Localization is the acceptance metric for repo-QA file-location accuracy.
- `swe-polybench` and `defects4c` are the acceptance metrics for cross-language drift.
- `codespecbench` / `pvbench` are the calibration suites for implementation-check and patch-review verdicts respectively.
- External adapter network calls are disabled in Phase 10 CI.

---

## 9. RDS Feature Computation

### 9.1 Purpose

RDS v0.2 is a six-axis difficulty feature vector logged per instance until a validated cross-benchmark regression model is published. It stratifies variance in benchmark results without leaking training-data membership signal.

### 9.2 `RDSFeatureVector` Model

Required fields:

```text
RDSFeatureVector
  instance_id
  eval_run_id
  files_touched
  chain_depth
  cross_file_dataflow
  ambient_warning_load
  test_brittleness
  memorisation_distance
  computed_ts
  source_snapshot_id
```

Feature definitions:

- `files_touched`: count of gold-patch changed files.
- `chain_depth`: maximum call-chain depth in the subgraph anchored at changed symbols.
- `cross_file_dataflow`: count of cross-file dataflow edges from Phase 5/6 graph intersecting the gold patch.
- `ambient_warning_load`: count of SARIF alerts in the affected files at the time of the issue, from Phase 6.
- `test_brittleness`: ratio of tests that would fail from a random single-line perturbation of the gold patch file, sampled from mutation metadata where available.
- `memorisation_distance`: inverse lexical distance between the issue text and the nearest known training-adjacent instance; high distance = lower memorisation risk. Uses a null estimate (0.5) until the model-specific memorisation probe is calibrated.

### 9.3 `compute_rds_features` Tool

Purpose: compute and store the RDS feature vector for a given issue instance.

Input:

```text
instance_id
repo?
snapshot?
gold_patch_ref?
```

Output:

- `RDSFeatureVector`.
- Provenance with graph snapshot ID, SARIF run IDs used, and computation timestamp.
- Diagnostics for each axis where values could not be computed.

Rules:

- Store result per instance in the eval artefact store.
- Log `memorisation_distance` as `0.5` (null estimate) in Phase 10 with a flag `calibrated: false`.
- Missing graph data produces an `unknown` value per axis, not zero.
- The feature vector is logged until the cross-benchmark regression is published; no release gate depends on it in Phase 10.

Permissions:

- Required mode: read/search.
- Path scope: registered repos.
- Network: none.
- Side effect: writes artefact store.

Tests:

- Feature vector computed for smoke fixture.
- Missing graph data produces diagnostic, not error.
- `memorisation_distance` is `0.5` with `calibrated: false` flag.
- Feature vector round-trips through JSON.

---

## 10. FL Metrics

### 10.1 Purpose

Fault-localisation accuracy is the leading predictor of repair success. Phase 10 must compute and log FL metrics per instance and in aggregate.

### 10.2 FL Metric Definitions

- `fl_top1_correct`: gold file appears in position 1 of ranked suspects.
- `fl_top3_correct`: gold file appears in top-3 of ranked suspects.
- `fl_topN_correct`: gold file appears in top-N where N is the phase-9 budget used.
- `fl_conditioned_repair_rate`: fraction of instances where the repair is correct given top-1 or top-3 FL is correct. Reported separately.

### 10.3 Multi-File Instances

Rules:

- For multi-file gold patches, `fl_top1_correct` requires all gold files in the top-K set where K equals the number of gold files.
- `fl_top3_correct` requires all gold files within the top-(3 × gold_count) set.
- Single-file and multi-file instances must be reported separately in aggregate metrics.

### 10.4 `FLMetricsAggregator` Model

Required fields:

```text
FLMetricsAggregator
  eval_run_id
  instance_count
  single_file_count
  multi_file_count
  top1_rate
  top3_rate
  topN_rate
  fl_conditioned_repair_rate
  per_instance_results
  per_language_breakdown
```

### 10.5 Mandatory Reporting Rule

The FL-conditioned repair rate must always be reported alongside the overall repair rate. Reporting only the unconditional resolve-rate without the FL-conditioned rate is not acceptable.

---

## 11. Operational-Quality Metrics

### 11.1 Purpose

Every eval run must report operational-quality metrics alongside task-accuracy metrics. Task accuracy without operational evidence is insufficient for release-gate claims.

### 11.2 `OperationalQualityMetrics` Model

Required fields:

```text
OperationalQualityMetrics
  eval_run_id
  process_compliance_rate
  trace_replay_success_rate
  policy_violation_count
  budget_hard_stop_count
  incident_recidivism_rate
  promotion_precision_placeholder
  cost_per_accepted_verdict
  readiness_delta
  computed_ts
```

Metric definitions:

- `process_compliance_rate`: fraction of instances where the run record includes all required event types (tool call, gate result, budget event, final verdict).
- `trace_replay_success_rate`: fraction of instances where a stored run record can be deserialized and its gates replayed without missing artefact references.
- `policy_violation_count`: total count of tool calls that were denied by the permission policy across all instances.
- `budget_hard_stop_count`: total count of instances that hit a context or token budget limit.
- `incident_recidivism_rate`: placeholder: fraction of instances that open an incident matching a previously seen incident pattern (zero until Phase 13 workflow is in place).
- `promotion_precision_placeholder`: placeholder metric for reviewed lesson promotion quality (zero until Phase 17).
- `cost_per_accepted_verdict`: total tokens / accepted verdicts; accepted verdict requires all deterministic gates to pass.
- `readiness_delta`: difference in AI-readiness score between the run and the previous stored report.

### 11.3 Tests

Required tests:

- Metrics serialise and deserialise.
- Zero-violation run produces expected zeros for policy/budget fields.
- `process_compliance_rate` detects missing gate-result event.

---

## 12. Structural Maintainability Oracle Adapter

### 12.1 Purpose

A patch that passes visible tests can still fail a structural maintainability check. The oracle adapter exposes six properties that the Phase 11 patch-review gate and Phase 14 implementation-check workflow will use.

### 12.2 Oracle Properties

Properties:

- `change_locality`: how many modules or packages are touched relative to the size of the change.
- `dependency_direction`: whether the change introduces a dependency inversion or violates the project's layering model.
- `responsibility_decomposition`: whether changed functions/classes remain single-responsibility.
- `reuse_of_abstractions`: whether the change introduces a new abstraction that duplicates an existing one.
- `side_effect_isolation`: whether functions that previously had no observable side effects now acquire them.
- `testability`: whether changed symbols become harder to test in isolation (more dependencies injected, more global state accessed).

### 12.3 `MaintainabilityOracleResult` Model

Required fields:

```text
MaintainabilityOracleResult
  oracle_run_id
  diff_id
  change_locality_score
  dependency_direction_pass
  responsibility_pass
  reuse_pass
  side_effect_pass
  testability_pass
  overall_pass
  findings
  diagnostics
  computed_ts
```

### 12.4 Phase 10 Scope

In Phase 10, the oracle adapter:

- Is implemented as a lightweight rule-based analyser.
- Reads the diff and the affected graph slice from Phase 9/5.
- Does not call an LLM for structural judgement in Phase 10.
- Produces a `pass/fail` per property with evidence from the graph.
- Exports a result that Phase 11 can consume without re-deriving.

### 12.5 Tests

Required tests:

- Oracle returns correct locality score for smoke diff.
- Dependency-direction violation detected for known fixture.
- Overall pass computed correctly from per-property results.

---

## 13. AI-Readiness Report Generator

### 13.1 Purpose

The AI-readiness report scores the repository and project artefacts across five axes to quantify how well the project supports safe autonomous agent operations.

### 13.2 Axes and Scoring

Axes and maximum scores (5 points each, total 25):

- Agent config: `AGENTS.md` present, HC1-HC6 enforced, runtime overlays non-relaxing, permission profiles present.
- Documentation: spec, ADRs, API docs, runbook, and rollback path present and current.
- CI/CD: lint, type-check, tests, secrets scan, SAST, dependency scan, and harness regression passing.
- Code structure: layering consistent with graph, test coverage >85% core, no obvious dead code.
- Security: no hardcoded secrets in scan, dependency scan clean, SARIF alert count within threshold, redaction policy configured.

Stage thresholds (from architecture §1.1):

- `S0 → S1`: 5 total, at least 1 per axis.
- `S1 → S2`: 12 total, at least 2 per axis.
- `S2 → S3`: 18 total, at least 3 per axis.
- Stable `S3`: 22 total, at least 4 per axis.

### 13.3 `AIReadinessReport` Model

Required fields:

```text
AIReadinessReport
  report_id
  repo_id
  eval_run_id
  harness_stage
  agent_config_score
  documentation_score
  ci_cd_score
  code_structure_score
  security_score
  total_score
  stage_threshold_met
  axis_findings
  readiness_delta_from_last
  no_regression_check_pass
  computed_ts
```

### 13.4 No-Regression Rule

A harness change fails unless any readiness-axis drop is tied to an explicit reviewed waiver or incident. Phase 10 must record the readiness delta so Phase 18 can enforce the no-regression rule.

### 13.5 Tests

Required tests:

- Report generates for smoke fixture repo.
- Stage threshold computed correctly.
- Readiness delta computed against prior stored report.
- Zero-score axis is explicit, not silently zero.

---

## 14. Contamination Canary and Suite Freshness

### 14.1 Contamination Canary

A contamination canary is a known probe instance that verifies the model has not seen the evaluation set during training.

Canary model fields:

```text
ContaminationCanaryResult
  canary_id
  eval_run_id
  model_id
  probe_instance_id
  memorisation_distance_raw
  canary_verdict
  canary_ts
```

Canary verdict values:

- `clean`: no strong memorisation signal.
- `suspect`: possible memorisation, flag in report.
- `contaminated`: strong memorisation signal, block release-gate claim.
- `unknown`: canary probe not available or not calibrated for this model.

Rules:

- Phase 10 uses `unknown` for all canaries until a calibrated probe is added.
- Canary result must appear in every `EvalRun` report.
- `contaminated` canary must be reported alongside, not hidden inside, the aggregate resolve-rate number.

### 14.2 Suite Freshness

Fields:

```text
FreshnessRecord
  suite_id
  suite_version
  median_age_days
  oldest_instance_ts
  newest_instance_ts
  last_refresh_ts
  freshness_check_ts
```

Rules:

- `swe-bench-live` must be refreshed at least monthly for external-quality reporting.
- If `median_age_days > 30`, include a freshness warning in the eval report.
- `swd-bench` freshness must also be tracked when used for repo-QA file-location accuracy.

---

## 15. Flaky-Test Detection

### 15.1 Purpose

Tests that pass or fail non-deterministically corrupt FL-conditioned repair rate and gate metrics. Flaky instances must be detected and excluded before aggregation.

### 15.2 `FlakyTestRecord` Model

Required fields:

```text
FlakyTestRecord
  instance_id
  eval_run_id
  flaky_flag
  entropy_score
  rerun_count
  pass_count
  fail_count
  detection_method
  excluded_from_aggregate
```

### 15.3 Detection Methods

Supported methods in Phase 10:

- `rerun_entropy`: run the test multiple times and compute pass/fail entropy. If entropy > threshold (default 0.3), flag as flaky.
- `known_flaky_list`: allow a per-suite static flaky instance list to pre-exclude instances.
- `deterministic_only`: mark all instances that depend on external services or wall-clock time as suspect.

### 15.4 Tests

Required tests:

- Flaky instance excluded from aggregate FL metrics.
- Non-flaky instance not excluded.
- `FlakyTestRecord` stores rerun evidence.

---

## 16. Prompt, Manifest, and Tool-Description Regression Adapter

### 16.1 Purpose

Prompt, manifest, and MCP tool-description changes must be testable independently of code tests. The regression adapter bridges the evaluation harness to the Phase 4 regression fixture store.

### 16.2 Adapter Responsibilities

The adapter should:

- Load stored prompt/tool-descriptor snapshots from Phase 4's regression fixtures.
- Compare them against current registered prompts and tool descriptors.
- Detect: new fields, removed fields, changed descriptions, changed permission metadata, changed refusal behavior.
- Report detected changes as regression findings.
- Classify findings as: `compatible`, `policy-relevant`, `breaking`, or `unknown`.

### 16.3 `ManifestRegressionResult` Model

Required fields:

```text
ManifestRegressionResult
  run_id
  eval_run_id
  scope
  changed_items
  findings
  overall_verdict
  computed_ts
```

### 16.4 Integration with Eval Run

Every eval run should include a `ManifestRegressionResult`. A `breaking` or `policy-relevant` finding does not block the eval run but must appear in the eval report and the `HarnessConditionSheet`.

---

## 17. `record_eval_result` Tool

### 17.1 Purpose

Store T1-T4 harness outputs, suite freshness, contamination canaries, resolve-rate conditioned on FL, PoC+ pass-rate, and per-clause ECE.

### 17.2 Input

```text
eval_run_id
suite_id
metrics
harness_condition_id
rds_summary_ref?
contamination_result?
freshness_record?
fl_metrics?
operational_metrics?
maintainability_oracle_results?
```

### 17.3 Output

- `EvalRun` record with all referenced artefacts stored.
- `code-intelligence://eval/{run_id}` resource published.
- Eval update notification emitted.

### 17.4 Rules

Rules:

- Every stored eval result must include a `HarnessConditionSheet`.
- Missing FL metrics must be explicit, not silently absent.
- Contamination canary result must be present even if `unknown`.
- Suite freshness warning is included if `median_age_days > 30`.
- ECE bucket fields are stored as null in Phase 10; they are populated by Phase 11's calibration pipeline.

### 17.5 Tests

Required tests:

- `record_eval_result` stores an `EvalRun`.
- Missing `HarnessConditionSheet` fails validation.
- Stored result is retrievable via resource.
- `code-intelligence://eval/{run_id}` resource returns typed payload.

---

## 18. `run_eval_suite` Tool

### 18.1 Purpose

Launch a T1-T4 harness run, compute metrics, store results, and return a task handle for polling.

### 18.2 Input

```text
suite: "t1" | "t2" | "t3" | "t4" | "smoke"
target?
instance_ids?
model_backend?
policy_id?
harness_condition?
null_mode?
```

### 18.3 Output

- `TaskCreateResult` for the eval run task.
- On completion: `EvalRun` reference with aggregate metrics, RDS summary, FL metrics, operational metrics, and `HarnessConditionSheet`.

### 18.4 Behavior

1. Create `EvalRun` record and task.
2. Load instances from adapter.
3. For each instance: compute RDS features, run localisation pipeline (or null mode), collect gate events, compute FL and operational metrics.
4. Detect and flag flaky instances.
5. Run manifest regression adapter.
6. Assemble `HarnessConditionSheet`.
7. Call `record_eval_result`.
8. Emit `notifications/resources/updated` for `code-intelligence://eval/{run_id}`.
9. Return completed task result.

### 18.5 Permissions

- Required mode: read/search for null mode; read/search/execute for pipeline mode.
- Path scope: registered repos and workspace store.
- Network: none.
- Side effect: writes artefact store and eval records.

### 18.6 Tests

Required tests:

- Smoke T1 run completes in null mode.
- Task is created and polled.
- Completed result includes `EvalRun` reference.
- Resource update notification emitted on completion.
- T3/T4 returns `not_implemented` status gracefully.

---

## 19. `code-intelligence://eval/{run_id}` Resource

### 19.1 Purpose

Serve eval-run metadata, aggregate metrics, suite freshness, and RDS summary for MCP clients and operational monitoring.

### 19.2 Payload

Payload should include:

- `eval_run_id`
- `suite_id` and `suite_version`
- `model_backend` and `toolset_hash`
- `harness_condition_id`
- Aggregate FL metrics (top-1, top-3, top-N, FL-conditioned repair rate)
- Operational metrics summary
- Contamination canary result
- Suite freshness record
- RDS feature distribution summary
- Manifest regression verdict
- Per-instance results artefact reference
- Created and completed timestamps

### 19.3 Subscription

The eval resource is subscribable. Clients can subscribe to:

- `code-intelligence://eval/{run_id}` for a specific run.
- `code-intelligence://eval/latest` (optional convenience alias) for the most recent completed run.

Emit `notifications/resources/updated` when a new eval run completes.

### 19.4 Tests

Required tests:

- Resource returns typed payload for completed eval run.
- Missing eval run returns typed not-found.
- Subscription emits notification on eval completion.

---

## 20. Private `evaluate` Skill Template

### 20.1 Purpose

The private `evaluate` template is the session-level orchestration plan for a structured eval run. It instructs the agent how to launch `run_eval_suite`, interpret results, and log metrics before making quality claims.

### 20.2 Template Arguments

```text
suite: T1 | T2 | T3 | T4
target?
null_mode?
```

### 20.3 Template Structure

The template should instruct the agent to:

1. Read current `HarnessConditionSheet` metadata from the server.
2. Launch `run_eval_suite` as a task.
3. Poll until completion.
4. Read `code-intelligence://eval/{run_id}` resource.
5. Log: resolve-rate, FL-conditioned repair rate, PoC+ pass-rate, repo-QA accuracy, cross-language drift, RDS v0.2 features, contamination canaries, and operational-quality metrics.
6. Report suite freshness and manifest regression verdict.
7. If contamination canary is `suspect` or `contaminated`, flag prominently before stating resolve-rate.
8. If operational metrics show process compliance < 90%, include operational warning.
9. Conclude with a structured summary including `HarnessConditionSheet` reference.

### 20.4 Rules

Rules:

- The template must explicitly state the `swe-bench-live` headline requirement when reporting external-quality claims.
- The template must never report resolve-rate without FL-conditioned repair rate.
- The template must never report a quality claim from a run with a `contaminated` canary.
- LLM-as-judge results must not be presented as deterministic gate outputs.

### 20.5 Tests

Required tests:

- Template renders with all required arguments.
- Template includes contamination warning placeholder.
- Template includes FL-conditioned rate requirement.
- Template snapshot is stable.

---

## 21. Test Plan

### 21.1 Model Tests

Required:

- `EvalRun` round-trip.
- `HarnessConditionSheet` round-trip.
- `RDSFeatureVector` round-trip.
- `EvalInstanceResult` round-trip.
- `OperationalQualityMetrics` round-trip.
- `AIReadinessReport` round-trip.
- `ContaminationCanaryResult` round-trip.
- `FreshnessRecord` round-trip.
- Missing required fields fail validation.

### 21.2 T1 Runner Tests

Required:

- T1 null-mode run completes.
- Five required instance types all produce `EvalInstanceResult`.
- FL metrics computed per instance.
- Aggregate metrics match per-instance aggregation.
- `HarnessConditionSheet` attached to every run.
- Flaky instance excluded from aggregate.
- Manifest regression result attached.

### 21.3 Tool Tests

Required:

- `run_eval_suite` task lifecycle.
- `compute_rds_features` for smoke instance.
- `record_eval_result` stores eval run.
- Resource read after `record_eval_result`.
- Permission descriptors for all tools.
- Refusal for out-of-scope suite type.

### 21.4 Resource Tests

Required:

- `code-intelligence://eval/{run_id}` returns payload.
- Missing run returns typed not-found.
- Subscription emits notification.

### 21.5 Template Tests

Required:

- `evaluate` template renders.
- Template snapshot stable.
- Template includes contamination and FL requirements.

---

## 22. Work Packages

### P10.1 Eval Run Model

Build:

- `EvalRun`, `EvalInstanceResult`, `RDSFeatureVector` models.
- Validation helpers.
- JSON serialization.

Deliverables:

- `evaluation/models.py`
- Model tests.

Acceptance:

- Models round-trip and validate.

### P10.2 Harness Condition Sheet

Build:

- `HarnessConditionSheet` model.
- Compact, JSON, and diff-key renderers.
- Comparison helper.

Deliverables:

- `evaluation/harness_condition.py`
- HCS tests.

Acceptance:

- Sheet renders and compares correctly.

### P10.3 RDS Feature Computation

Build:

- `RDSFeatureVector` computation logic.
- Per-axis graph, SARIF, and perturbation queries.
- Null-estimate for `memorisation_distance`.

Deliverables:

- `evaluation/rds_features.py`
- `compute_rds_features` tool handler.
- RDS tests.

Acceptance:

- Feature vector computed for smoke instance with correct axis values.

### P10.4 FL Metrics

Build:

- `FLMetricsAggregator`.
- Single-file and multi-file metric computation.
- FL-conditioned repair rate computation.

Deliverables:

- `evaluation/fl_metrics.py`
- FL metric tests.

Acceptance:

- Top-1, top-3, top-N rates computed from smoke fixture results.

### P10.5 Operational Metrics

Build:

- `OperationalQualityMetrics` computation from run records.
- Process-compliance rate from event coverage.
- Trace-replay success rate.

Deliverables:

- `evaluation/operational_metrics.py`
- Operational metric tests.

Acceptance:

- Metrics produced for a Phase 4 test run record fixture.

### P10.6 Benchmark Adapter and Smoke Fixtures

Build:

- `BenchmarkAdapter` interface.
- `LocalSmokeAdapter`.
- Smoke fixture directory with five required instance types.
- Freshness and canary methods.

Deliverables:

- `evaluation/benchmark_adapter.py`
- `evaluation/smoke_adapter.py`
- Fixture instances.

Acceptance:

- Adapter loads all five required smoke instances.

### P10.7 T1 Smoke Runner

Build:

- T1 runner loop.
- Null-mode runner.
- Per-instance result assembly.
- Aggregate metric assembly.

Deliverables:

- `evaluation/t1_runner.py`
- T1 runner tests.

Acceptance:

- T1 null-mode run completes all smoke instances.

### P10.8 T2 Skeleton and T3/T4 Stubs

Build:

- T2 runner skeleton with baseline comparison.
- T3/T4 not-implemented stubs.

Deliverables:

- `evaluation/t2_runner.py`
- T2/T3/T4 stub tests.

Acceptance:

- T2 skeleton completes; T3/T4 return explicit stubs.

### P10.9 Maintainability Oracle and AI-Readiness Report

Build:

- `MaintainabilityOracleAdapter` with six properties.
- `AIReadinessReport` generator.
- Stage threshold computation.
- No-regression check.

Deliverables:

- `evaluation/maintainability_oracle.py`
- `evaluation/ai_readiness.py`
- Oracle and readiness tests.

Acceptance:

- Oracle and readiness report produce typed results for smoke repo.

### P10.10 Contamination and Flaky-Test Support

Build:

- `ContaminationCanaryResult` model and null probe.
- `FlakyTestRecord` model.
- Rerun-entropy detector.
- Known-flaky list loader.

Deliverables:

- `evaluation/contamination.py`
- `evaluation/flaky_detector.py`
- Contamination and flaky tests.

Acceptance:

- Canary result stored; flaky instance excluded from aggregate.

### P10.11 Manifest Regression Adapter

Build:

- `ManifestRegressionResult` model.
- Snapshot comparison logic.
- Classification of changes.

Deliverables:

- `evaluation/regression_adapter.py`
- Regression adapter tests.

Acceptance:

- Changed tool descriptor detected and classified.

### P10.12 `run_eval_suite` Tool and Resource

Build:

- `run_eval_suite` task-capable tool handler.
- `record_eval_result` tool handler.
- `code-intelligence://eval/{run_id}` resource handler.
- Eval update notification emitter.

Deliverables:

- `mcp_server/tools/eval.py`
- `mcp_server/resources/eval.py`
- Tool and resource tests.

Acceptance:

- MCP client can launch eval suite, poll task, and read eval resource.

### P10.13 `evaluate` Template

Build:

- `evaluate.md` private skill template.
- Template regression test.

Deliverables:

- `skills/evaluate.md`
- Template test.

Acceptance:

- Template renders; snapshot stable; contamination and FL requirements present.

---

## 23. Suggested Implementation Order

Recommended order:

1. Eval run and instance result models.
2. `HarnessConditionSheet` model and renderer.
3. `RDSFeatureVector` model and `compute_rds_features` computation.
4. FL metrics.
5. Benchmark adapter interface and smoke adapter.
6. Smoke fixture instances (five required types).
7. T1 null-mode runner.
8. Operational-quality metrics.
9. Contamination canary and flaky-test support.
10. `record_eval_result` tool and eval resource.
11. `run_eval_suite` task-capable tool.
12. T2 skeleton and T3/T4 stubs.
13. Maintainability oracle adapter.
14. AI-readiness report generator.
15. Manifest regression adapter.
16. `evaluate` private skill template.

Reasoning:

- Models and metrics must exist before any runner can store results.
- Smoke adapter and T1 runner validate the pipeline before adding external suites.
- `record_eval_result` and the resource must exist before the `run_eval_suite` wrapper.
- Operational metrics depend on run records from the Phase 4 task store.

---

## 24. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 10 |
|---|---|
| Phase 11 - Patch review | `HarnessConditionSheet`, `MaintainabilityOracleResult`, `BenchmarkAdapter` interface, patch-review eval integration hooks |
| Phase 12 - SAST repair | `EvalRun` model, SARIF delta metric tracking, `run_eval_suite` for SAST-repair benchmark instances |
| Phase 13 - Bug-resolve | `EvalRun`, FL metrics, `HarnessConditionSheet` in every workflow run, smoke instances for T1 regression after repair |
| Phase 14 - Implementation-check | `EvalInstanceResult`, `codespecbench` adapter skeleton, ECE bucket fields in `record_eval_result` |
| Phase 15 - Blast radius | Cross-language drift metric from T2 regression baseline |
| Phase 16 - Dynamic traces | Perturbation runner skeleton, `test_brittleness` RDS axis |
| Phase 17 - Memory | `outcome` and `utility` fields in `EvalInstanceResult` for trajectory labelling |
| Phase 18 - Release gates | T1-T4 ladder, `AIReadinessReport`, contamination canary policy, manifest regression adapter |
| Phase 19 - Distribution | Eval resource, `run_eval_suite` tool, `evaluate` template |

---

## 25. Exit Criteria Mapping

Source Phase 10 exit criterion:

- A smoke eval run produces stored metrics.

Concrete acceptance:

- T1 null-mode run completes all five required instances.
- `EvalRun` is stored with FL metrics, operational metrics, and RDS features.
- `EvalRun` is retrievable via `code-intelligence://eval/{run_id}`.

Source Phase 10 exit criterion:

- Every eval run records a Harness Condition Sheet.

Concrete acceptance:

- `HarnessConditionSheet` is required field on `EvalRun`.
- Missing sheet fails `record_eval_result` validation.
- Sheet comparison detects model or manifest-hash drift.

Source Phase 10 exit criterion:

- RDS features are computed and saved per instance.

Concrete acceptance:

- `compute_rds_features` produces `RDSFeatureVector` for all smoke instances.
- `memorisation_distance` is logged as null estimate with `calibrated: false`.
- Missing graph data produces per-axis diagnostics, not silent zeros.

Source Phase 10 exit criterion:

- Eval reports are reproducible from stored artefacts.

Concrete acceptance:

- `artefact_manifest_ref` on `EvalRun` resolves to all referenced per-instance result artefacts.
- Replay helper can re-compute aggregate metrics from stored per-instance results.

Source Phase 10 exit criterion:

- Eval reports include operational metrics beside task metrics.

Concrete acceptance:

- `OperationalQualityMetrics` attached to every completed `EvalRun`.
- `process_compliance_rate` computed from run event coverage.

Source Phase 10 exit criterion:

- Baseline suite contains at least one ambiguity task, one security-sensitive task, and one maintainability task.

Concrete acceptance:

- Smoke fixture includes instances tagged `ambiguity`, `security`, and `maintainability`.
- T1 runner log identifies each required type.

Source Phase 10 exit criterion:

- Manifest/tool-description regression cases can fail independently of code tests.

Concrete acceptance:

- Manifest regression adapter produces `ManifestRegressionResult` per eval run.
- A changed tool descriptor fixture triggers a `policy-relevant` finding.

---

## 26. Definition Of Done

Phase 10 is done when:

- `EvalRun`, `HarnessConditionSheet`, and `RDSFeatureVector` models are defined and tested.
- T1 null-mode runner completes all five required smoke instance types.
- FL metrics (top-1, top-3, top-N, FL-conditioned repair rate) are computed per instance and in aggregate.
- Operational-quality metrics are computed and stored per eval run.
- `compute_rds_features` returns a six-axis vector with null estimates for uncalibrated axes.
- `record_eval_result` stores eval runs with all required fields.
- `run_eval_suite` task-capable tool launches, completes, and returns an `EvalRun` reference.
- `code-intelligence://eval/{run_id}` resource is routable and returns typed payload.
- Subscription emits update notification on eval completion.
- `contamination_canary_result` is stored in every eval run even when `unknown`.
- Flaky instances are excluded from aggregate FL metrics.
- Manifest regression adapter detects and classifies prompt/tool-descriptor changes.
- AI-readiness report is generated for the fixture repo.
- Private `evaluate` template renders and snapshot is stable.
- All mandatory reporting rules are enforced by the runner and template.

---

## 27. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| FL metrics computed incorrectly for multi-file instances | Inflated top-1 rate, misleading quality claims | Require all gold files within budget-adjusted top-K; separate single-file and multi-file rates |
| Contamination canary absent | Contaminated results reported without warning | Require canary result (even `unknown`) on every `EvalRun`; `contaminated` canary must appear in report header |
| RDS axes silently zero on missing data | Feature vector misleads difficulty stratification | Require per-axis diagnostic field; `unknown` is the correct value when graph data is absent |
| `HarnessConditionSheet` skipped under pressure | Benchmark numbers incomparable across models or configs | Fail `record_eval_result` validation when `harness_condition_id` is missing |
| Flaky instances inflate failure rate | Low process-compliance or gate-failure rate looks like quality regression | Detect and flag flaky instances; exclude from aggregate; store exclusion reason |
| Operational metrics require Phase 4A run events | Metrics are zero or meaningless in Phase 10 | Compute on available events; explicitly label as `partial` when event coverage is low |
| T2 baseline regression obscured by suite-version drift | Apparent regression is actually a harder suite | Track `suite_version` and `suite_median_age_days` in `EvalRun`; flag version difference in regression report |
| Eval resource grows unbounded | Resource read response too large | Cap at manifest-plus-summary; full instance results behind artefact reference |
| `evaluate` template reports quality claims without operational evidence | Users over-trust single resolve-rate number | Enforce FL-conditioned rate and operational metrics requirement in template and in tool output |

---

## 28. Phase 10 Completion Report Template

When Phase 10 implementation is complete, report:

```text
Phase 10 completion report

Implemented:
- EvalRun model:
- HarnessConditionSheet model and renderer:
- RDSFeatureVector model (6 axes):
- FL metrics:
- Operational-quality metrics:
- Benchmark adapter interface:
- LocalSmokeAdapter:
- Smoke fixture instances (count, types):
- T1 null-mode runner:
- T2 regression skeleton:
- T3/T4 stubs:
- Flaky-test detector:
- Contamination canary support:
- Maintainability oracle adapter:
- AI-readiness report generator:
- Manifest regression adapter:
- run_eval_suite task-capable tool:
- compute_rds_features tool:
- record_eval_result tool:
- code-intelligence://eval/{run_id} resource:
- evaluate private skill template:

Verification:
- Model round-trip tests:
- T1 null-mode run:
- FL metric tests:
- Operational metric tests:
- Resource tests:
- Tool tests:
- Template snapshot:
- Manifest regression tests:

Exit criteria:
- Smoke eval run produces stored metrics:
- Every eval run records HarnessConditionSheet:
- RDS features computed per instance:
- Eval reports reproducible from artefacts:
- Operational metrics beside task metrics:
- Required smoke instance types present:
- Manifest regression cases independent of code tests:

Known limitations:
-

Follow-up for Phase 11:
-
```

---

## 29. Minimal First Slice Within Phase 10

If Phase 10 needs to be split further, implement this first:

1. `EvalRun` and `EvalInstanceResult` models.
2. `HarnessConditionSheet` model with compact renderer.
3. `RDSFeatureVector` model with all axes as null estimates.
4. `FLMetricsAggregator` with top-1/top-3/top-N.
5. `LocalSmokeAdapter` with five required fixture instances.
6. T1 null-mode runner.
7. `compute_rds_features` tool.
8. `record_eval_result` tool.
9. `code-intelligence://eval/{run_id}` resource.
10. `run_eval_suite` task-capable tool (smoke/T1 target only).
11. Basic contamination canary model (all `unknown`).
12. Private `evaluate` template stub.

This minimal slice establishes the measurement baseline before Phase 11 patch-review or Phase 13 bug-resolve workflows produce eval-grade output. It does not pretend T2-T4 external benchmarks are available.
