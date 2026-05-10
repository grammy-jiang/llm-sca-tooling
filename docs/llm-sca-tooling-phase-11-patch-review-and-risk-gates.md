# LLM-SCA Tooling Phase 11 Implementation Plan: Patch Review and Risk Gates

> Date: 2026-05-09
> Repository name: `evidence-sca`
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 11 - Patch Review and Risk Gates
> Primary objective: build the safety and correctness gate that all repair workflows must pass — multi-axis patch review, SARIF delta, maintainability gate, DryRUN prediction contract, patch-risk classifier, MCP Sampling integration with fallback, and `run_patch_review` / `classify_patch_risk` tools.

---

## 1. Phase Summary

Phase 11 is the first workflow-safety phase of `evidence-sca`. Phases 1-10 built the index, MCP server, SARIF layer, fault localisation, and the evaluation baseline. Phase 11 adds the gate layer that any patch-producing workflow must pass before it can recommend merge.

The central rule for this phase is:

```text
A patch is not safe to merge when deterministic gates pass alone.
A `safe` patch-risk label requires: deterministic gates pass AND calibrated classifier
confidence is above threshold AND operational run is process-compliant.
New critical SARIF alerts, broken contracts, failing required tests, trace-incomplete runs,
budget-exhausted runs, or out-of-scope writes override `safe` unconditionally.
`unknown` is returned when classifier calibration data is missing for the patch's
language and rule family.
```

Phase 11 should implement:

- Diff parser and changed-symbol detector.
- AST diff feature extraction.
- Graph context extraction around changed symbols.
- SARIF before/after delta.
- Test result delta model.
- Vulnerability prior features from CWE/rule-family calibration data where available.
- Interface compatibility check.
- Behavioural drift placeholder.
- MCP Sampling integration for adapted four-agent patch audit with fallback path.
- DryRUN prediction contract.
- Scope and permission audit.
- Structural maintainability gate.
- Patch-risk classifier interface with typed feature contract.
- Initial deterministic risk policy before trained classifier is available.
- Four review axes: correctness, security, performance, compatibility.
- Merge/block recommendation policy.
- Operational-review integration.
- `run_patch_review` and `classify_patch_risk` tools.
- `audit` private skill template for patches.
- `risk-classify` private skill template.

### Architecture Coverage

Phase 11 covers:

- F6 patch-review and patch-risk classification.
- F11 operational-run compliance for patch-producing and patch-review workflows.
- Private `audit` skill template for patch mode.
- `run_patch_review` tool.
- `classify_patch_risk` tool.
- DryRUN prediction contract.

Tools in this phase:

- `run_patch_review`
- `classify_patch_risk`

Private skill templates in this phase:

- `audit` (patch mode)
- `risk-classify`

### Inherited Paper Anchors

Use these anchors in Phase 11 issues, ADRs, and patch-review reports:

- `multi-agent-info-theory`
- `correct-not-safe`
- `redteam-apr`
- `compass`
- `pvbench`
- `logiceval`
- `why-llms-fail-secpatch`
- `predicatefix`
- `rig`

## Technology Stack

This phase uses the following libraries from `llm-sca-tooling-tech-stack.md`:

| Library/Tool | PyPI package | Version | Role in this phase |
|---|---|---|---|
| Python | — | 3.12+ | Runtime |
| uv | — | latest | Environment and dependency management |
| Pydantic v2 | `pydantic` | >=2.0 | `DryRUNPrediction`, `PatchRiskFeatureVector`, `PatchRiskResult`, `PatchReviewReport` schemas; `extra="forbid"` on all models |
| orjson | `orjson` | >=3.10 | Diff payload serialisation, risk-finding payload serialisation, all JSON I/O |
| NetworkX | `networkx` | >=3.3 | Graph context extraction around changed symbols — callers, callees, blast-radius seed |
| FastMCP + FastAPI | `fastmcp`, `fastapi` | >=2.0, >=0.115 | `run_patch_review` and `classify_patch_risk` MCP tool handlers |
| httpx | `httpx` | >=0.27 | `PolicyAwareHTTPClient` wrapping for HC5 |
| pytest + pytest-asyncio | `pytest`, `pytest-asyncio` | >=8.0, >=0.23 | Patch-review tests; `asyncio_mode="auto"` |

- All subprocess calls (Semgrep for SARIF delta computation) use `asyncio.create_subprocess_exec`; `subprocess.run` is forbidden.
- All tool handlers (`run_patch_review`, `classify_patch_risk`) and workflow functions are `async def`.
- Rich is restricted to the CLI layer; all other modules use `logging`.
- Pydantic models use `model_json_schema()` for schema export; no hand-written JSON schemas.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 11 depends on:

- Phase 1 schemas:
  - `Patch` and `RiskFinding` models
  - `Verdict` model with `risk_class`, `calibrated_probability`, and `ece_bucket`
  - `ContractArtifact` model
  - `RunRecord` and `RunEvent` models
- Phase 2 stores:
  - graph store with callers/callees, cross-file dataflow edges
  - SARIF run store from Phase 6
  - operational store from Phase 4A
- Phase 4 infrastructure:
  - task manager and task persistence
  - tool-description regression harness
  - Sampling capability detection record
- Phase 5 language backends:
  - cross-language interface links for compatibility check
- Phase 6 SARIF layer:
  - SARIF run store, alert fingerprinting, and delta utility
  - alert-to-graph binding
- Phase 7 interface plugins:
  - `InterfaceRecord` and `InterfaceOperation` for compatibility check
- Phase 9 fault localisation:
  - `LocalisationResult` and `ranked_candidates` as prior context for patch risk
- Phase 10 evaluation harness:
  - `MaintainabilityOracleResult` model
  - `HarnessConditionSheet` model
  - `EvalRun` model for patch-review calibration data

### Phase Outputs

Phase 11 should produce:

- `DiffRecord` model with unified-diff parsing.
- `ChangedSymbolRecord` model.
- `ASTDiffFeatures` model.
- `GraphContextRecord` for patch scope.
- `SARIFDelta` model (reusing Phase 6 delta utility).
- `TestDeltaRecord` model.
- `InterfaceCompatibilityResult` model.
- `DryRUNPrediction` model and contract.
- `ScopeAuditResult` model.
- `MaintainabilityGateResult` model (using Phase 10 oracle).
- `PatchRiskFeatureVector` model.
- `PatchRiskResult` model with `risk_class`, `calibrated_probability`, `ece_bucket`.
- `PatchReviewReport` model.
- `run_patch_review` tool handler.
- `classify_patch_risk` tool handler.
- `audit` skill template (patch mode).
- `risk-classify` skill template.
- Patch-review tests.

### Non-Goals

Do not implement these in Phase 11:

- Trained ML patch-risk classifier model (rule-based deterministic policy only in Phase 11).
- Calibrated ECE bucket values (placeholders only until external calibration data is available).
- Bug-resolve workflow (Phase 13).
- SAST alert repair (Phase 12).
- Implementation-check workflow (Phase 14).
- Blast-radius service (Phase 15).
- Dynamic trace capture (Phase 16).
- Memory or trajectory storage (Phase 17).
- Full production merge automation.

---

## 3. Recommended File Layout

Assuming package name `evidence_sca`:

```text
src/evidence_sca/
  patch_review/
    __init__.py
    models.py
    diff_parser.py
    symbol_detector.py
    ast_diff.py
    graph_context.py
    sarif_delta.py
    test_delta.py
    interface_compat.py
    dryrun.py
    scope_audit.py
    maintainability_gate.py
    risk_features.py
    risk_classifier.py
    risk_policy.py
    four_agent_audit.py
    sampling_integration.py
    report.py
    merge_policy.py
    operational_integration.py

  mcp_server/
    tools/
      patch_review.py

  skills/
    audit.md
    risk_classify.md

tests/
  patch_review/
    fixtures/
      diffs/
        safe_fix.diff
        vulnerable_fix.diff
        overfit_fix.diff
        scope_violation.diff
        missing_test_fix.diff
      sarif_before/
      sarif_after/
    test_diff_parser.py
    test_symbol_detector.py
    test_ast_diff.py
    test_graph_context.py
    test_sarif_delta.py
    test_test_delta.py
    test_interface_compat.py
    test_dryrun.py
    test_scope_audit.py
    test_maintainability_gate.py
    test_risk_features.py
    test_risk_classifier.py
    test_risk_policy.py
    test_four_agent_audit.py
    test_report.py
    test_merge_policy.py
    test_run_patch_review.py
    test_classify_patch_risk.py
    test_audit_template.py
    test_risk_classify_template.py
```

---

## 4. Diff Parser and Changed-Symbol Detection

### 4.1 `DiffRecord` Model

Required fields:

```text
DiffRecord
  diff_id
  diff_text
  diff_format
  changed_files
  hunks
  added_lines
  removed_lines
  net_lines
  snapshot_before_id
  snapshot_after_id
  provenance
```

### 4.2 `ChangedSymbolRecord` Model

Required fields:

```text
ChangedSymbolRecord
  diff_id
  file_path
  symbol_path
  symbol_type
  change_kind
  span_before
  span_after
  graph_node_id
  confidence
  is_generated
  is_public_api
  is_interface_boundary
```

`change_kind` values:

- `added`
- `removed`
- `modified_signature`
- `modified_body`
- `modified_docstring`
- `renamed`
- `unknown`

### 4.3 Changed-Symbol Detector

The detector must:

- Parse the unified diff.
- Map changed lines to symbol spans using the Phase 5 AST-based index.
- Match changed file paths to graph nodes.
- Classify each changed symbol by type and kind.
- Flag symbols at interface boundaries (Phase 7 plugin records).
- Flag generated-file changes (Phase 7 `GeneratedArtifactRecord`).
- Flag public API changes.
- Produce a diagnostic when symbol resolution fails (graph node absent or index stale).

### 4.4 Rules

Rules:

- Unknown symbol changes are not silently dropped; they produce `unknown` confidence entries.
- Generated-file changes must be flagged and their source contract identified.
- Interface-boundary changes propagate to the compatibility check stage.
- Stale index must be flagged in the diff record diagnostics.

### 4.5 Tests

Required tests:

- Parser extracts hunks and file paths from unified diff.
- Symbol detector maps changed lines to graph nodes for fixture.
- Interface-boundary flag set for changed HTTP route.
- Generated-file flag set for changed proto stub.
- Stale index triggers diagnostic.

---

## 5. AST Diff Feature Extraction

### 5.1 Purpose

AST-level diff features are the first input dimension of the patch-risk classifier. They capture structural change properties that line counts miss.

### 5.2 `ASTDiffFeatures` Model

Required fields:

```text
ASTDiffFeatures
  diff_id
  changed_node_kinds
  edit_operation
  touched_symbol_count
  edit_distance_proxy
  generated_or_stub_flag
  signature_changed
  return_type_changed
  parameter_count_delta
  raises_new_exception
  security_sensitive_annotation_removed
  confidence
```

`edit_operation` values:

- `added_function`
- `removed_function`
- `signature_change`
- `body_change`
- `conditional_inserted`
- `conditional_removed`
- `loop_inserted`
- `loop_removed`
- `exception_handler_changed`
- `other`

### 5.3 Implementation Notes

In Phase 11:

- Use Tree-sitter (Phase 3 adapter) for structural change detection.
- If AST parse fails for the diff context, fall back to heuristic line-level features with `confidence: heuristic`.
- Do not call an LLM for AST diff interpretation.

---

## 6. Graph Context Extraction

### 6.1 Purpose

The graph context provides the classifier with the two-hop neighbourhood of changed symbols, cross-file dataflow, test coverage, and interface boundaries.

### 6.2 `GraphContextRecord` Model

Required fields:

```text
GraphContextRecord
  diff_id
  changed_symbol_ids
  two_hop_callers
  two_hop_callees
  cross_file_dataflow_edges
  interface_boundary_nodes
  tests_exercising_changed_nodes
  test_count
  coverage_available
  snapshot_id
  confidence
  diagnostics
```

### 6.3 Rules

Rules:

- Two-hop callers/callees are fetched using Phase 4's `find_callers`/`find_callees` logic.
- Cross-file dataflow edges are from the Phase 6-augmented graph.
- Tests are identified via `tests` edge type from Phase 3/5.
- Missing test evidence is `unknown`, not zero.
- Snapshot staleness must appear in diagnostics if the index is more than one commit behind the diff.

---

## 7. SARIF Before/After Delta

### 7.1 Purpose

The SARIF delta is the strongest deterministic gate: a new critical or security-class alert appearing after a patch is a near-automatic block condition.

### 7.2 Reusing Phase 6 Delta Utility

Phase 11 uses the SARIF delta utility from Phase 6 (`sarif_delta(before_run_id, after_run_id)`).

The delta produces:

- Alerts that appeared (new alerts).
- Alerts that disappeared (fixed alerts).
- Alerts that changed severity.
- Alerts that changed location.
- Alerts classified by CWE/rule-family.

### 7.3 Override Rules

Delta override conditions:

- New `critical` or `error` severity SARIF alert that was not present before the patch: override `safe` to `vulnerable` or `vulnerability-introducing`.
- New security-class alert (taint/nullness/injection/CWE category): override `safe` to `vulnerability-introducing`.
- These overrides are deterministic and do not depend on classifier confidence.

### 7.4 Tests

Required tests:

- Delta detects new critical alert in fixture.
- Delta detects disappeared alert (fixed).
- Override rule fires for new security-class alert.
- Empty delta on no-SARIF-change fixture.

---

## 8. Test Result Delta

### 8.1 `TestDeltaRecord` Model

Required fields:

```text
TestDeltaRecord
  diff_id
  tests_run
  tests_passed_before
  tests_passed_after
  tests_failed_before
  tests_failed_after
  newly_failing
  newly_passing
  reproduction_test_result
  poc_plus_result
  flaky_rerun_entropy
  confidence
```

`reproduction_test_result` values:

- `not_available`
- `generated`
- `executed_fail_before_pass_after`
- `executed_fail_both`
- `executed_pass_both`
- `flaky`

`poc_plus_result` values:

- `not_available`
- `passed`
- `failed`
- `flaky`

### 8.2 Rules

Rules:

- A failing required test after the patch is a block condition regardless of risk classifier output.
- PoC+ test failure for a vulnerability-class repair is a block condition.
- Generated reproduction tests that only pass after the patch but also pass before are not valid evidence.
- Flaky test results must be excluded from gate conclusions; they count as `unknown`.

---

## 9. Interface Compatibility Check

### 9.1 Purpose

Interface changes can break callers that the repository's own test suite does not cover. The compatibility check uses Phase 7 plugin data to find cross-language or cross-service consumers.

### 9.2 `InterfaceCompatibilityResult` Model

Required fields:

```text
InterfaceCompatibilityResult
  diff_id
  interface_type
  changed_operations
  affected_consumers
  breaking_changes
  candidate_changes
  generated_file_impact
  confidence
  diagnostics
```

### 9.3 Breaking Change Detection

Rules:

- Removed or renamed interface operation: `breaking`.
- Added required parameter without default: `breaking`.
- Changed return type: `breaking` or `candidate` depending on interface type.
- Added optional parameter: `compatible`.
- Generated-file change: report source contract that must also change.
- Low-confidence links (Phase 7 candidate edges) produce `candidate`, not `confirmed_breaking`.

---

## 10. DryRUN Prediction Contract

### 10.1 Purpose

A DryRUN prediction is a structured pre-execution specification of what the patch should do. After execution, the actual outcome is compared against the prediction. Mismatches are reportable residual risk, not silent discrepancies.

### 10.2 `DryRUNPrediction` Model

Required fields:

```text
DryRUNPrediction
  diff_id
  intended_behaviour_change
  expected_files_changed
  expected_test_cases_passing
  expected_test_cases_failing
  expected_positive_cases
  expected_negative_cases
  expected_edge_cases
  predicted_outputs
  predicted_side_effects
  stated_invariants
  stated_risks
  generator
  confidence
```

### 10.3 DryRUN vs Actual Mismatch

Mismatch model:

```text
DryRUNMismatch
  diff_id
  prediction_id
  mismatch_type
  predicted_value
  actual_value
  severity
  residual_risk_note
```

`mismatch_type` values:

- `extra_files_changed`
- `fewer_files_changed`
- `unexpected_test_failure`
- `unexpected_test_pass`
- `unexpected_side_effect`
- `invariant_violated`
- `stated_risk_materialised`

Rules:

- DryRUN mismatches are reportable; they must appear in the patch-review report.
- A `stated_risk_materialised` mismatch is an escalation candidate.
- Mismatches do not automatically block merge in Phase 11, but they degrade confidence from `analyser` to `heuristic` or `unknown`.

---

## 11. Scope and Permission Audit

### 11.1 Purpose

A patch can be functionally correct but produced by a run that violated permission policy, exceeded budget, or skipped required approval events. Such runs cannot receive an auto-merge recommendation.

### 11.2 `ScopeAuditResult` Model

Required fields:

```text
ScopeAuditResult
  run_id
  changed_paths
  allowlisted_paths
  out_of_scope_writes
  tool_calls_vs_mode
  network_use_vs_policy
  required_events_present
  approval_events_present
  denial_events_present
  budget_events_present
  compaction_events_present
  missing_required_events
  trace_complete
  process_verdict
```

`process_verdict` values:

- `process-compliant`
- `process-noncompliant`
- `trace-incomplete`
- `budget-exhausted`
- `unknown`

### 11.3 Override Rules

Process override conditions:

- `trace-incomplete`: removes auto-merge recommendation.
- `budget-exhausted`: removes auto-merge recommendation.
- `process-noncompliant`: removes auto-merge recommendation.
- Out-of-scope writes: override `safe` to `block`.
- Unapproved destructive tool use: override to `block`.

---

## 12. Structural Maintainability Gate

### 12.1 Purpose

A patch that passes tests can still violate structural maintainability properties. The maintainability gate uses the Phase 10 oracle adapter.

### 12.2 `MaintainabilityGateResult` Model

Required fields:

```text
MaintainabilityGateResult
  diff_id
  oracle_result_id
  change_locality_pass
  dependency_direction_pass
  responsibility_pass
  reuse_pass
  side_effect_pass
  testability_pass
  overall_pass
  findings
  block_merge
```

### 12.3 Block Condition

The maintainability gate can block merge even when all tests pass. Block conditions:

- `dependency_direction_pass: false`: the patch introduces a dependency inversion or violates layering.
- Three or more individual properties failing simultaneously.

### 12.4 Non-Block Findings

Single property failures other than dependency direction are `findings` that are reported but do not automatically block merge in Phase 11. They are flagged for human review.

---

## 13. Patch-Risk Classifier

### 13.1 Purpose

The patch-risk classifier combines all available features into a risk class and calibrated probability. The architecture targets macro-F1 ≥ 0.75 and ECE ≤ 0.10 before classifier output can block merges. In Phase 11 a deterministic rule-based policy serves until that bar is met.

### 13.2 `PatchRiskFeatureVector` Model

Required fields:

```text
PatchRiskFeatureVector
  diff_id
  ast_diff_features_ref
  sarif_delta_ref
  graph_context_ref
  test_delta_ref
  vulnerability_prior_cwe
  vulnerability_prior_rule_family
  vulnerability_prior_probability
  vulnerability_prior_calibrated
  interface_compatibility_ref
  dryrun_mismatch_count
  scope_audit_verdict
  maintainability_gate_pass
```

### 13.3 Risk Classes

Risk class enum:

- `safe`: deterministic gates pass, no overrides, classifier confidence above threshold.
- `correct-but-overfit`: visible tests pass but reproduction/PoC+ test, graph root-cause evidence, or certificate disagree.
- `vulnerable`: patch introduces a known-pattern vulnerability without fixing the root cause.
- `vulnerability-introducing`: patch adds new code that passes a vulnerability predicate not triggered before.
- `unknown`: calibration data missing, critical signal absent, or trace incomplete.

### 13.4 `PatchRiskResult` Model

Required fields:

```text
PatchRiskResult
  diff_id
  risk_class
  calibrated_probability
  ece_bucket
  feature_vector_ref
  active_overrides
  classifier_version
  calibration_family
  confidence
  policy_action
```

`policy_action` values:

- `merge-supporting`
- `review-required`
- `block`
- `unknown`

### 13.5 Deterministic Risk Policy (Phase 11 Default)

The deterministic risk policy applies when the trained classifier is unavailable or not calibrated for the patch's language/rule family:

Rule table:

1. New critical or security SARIF alert → `vulnerability-introducing`, `block`.
2. Failing required test → `correct-but-overfit` or `vulnerable`, `block`.
3. PoC+ failure for vulnerability-class repair → `vulnerable`, `block`.
4. Out-of-scope write detected → `block`.
5. Trace-incomplete, budget-exhausted, or process-noncompliant run → `unknown`, no auto-merge.
6. Breaking interface change detected → `review-required`.
7. Dependency-direction maintainability failure → `review-required`.
8. No SARIF alerts added, tests pass, no scope violations, no interface break → `safe`, `merge-supporting` (requires process-compliant run).

### 13.6 Calibration Gate

Before the trained classifier can gate merge decisions:

- Macro-F1 ≥ 0.75 on the patch's language and rule/CWE family.
- ECE ≤ 0.10 on the same family.
- Until met: deterministic policy is used; classifier output is logged as advisory.

---

## 14. Four-Agent Patch Audit with Sampling

### 14.1 Purpose

The adapted four-agent parallel check (`multi-agent-info-theory`) launches four independent reviewers simultaneously — correctness, security, performance, and compatibility — and aggregates their findings. MCP Sampling lets the server ask the client to invoke LLM sub-agents.

### 14.2 Review Axes

- **Correctness**: does the patch address the root cause? Does it introduce regressions?
- **Security**: does the patch introduce or suppress vulnerability signals? CWE/OWASP analysis.
- **Performance**: does the patch affect hot paths, allocations, lock-contention, or query plans?
- **Compatibility**: does the patch break interface, protocol, or serialisation contracts?

### 14.3 Sampling Integration

When MCP Sampling is available:

- The server sends four parallel `sampling/createMessage` requests to the client, one per axis.
- Each request includes: diff context, graph slice for changed symbols, SARIF delta, and axis-specific instructions.
- Responses are typed as `AxisFinding` records, not free-form text.

When Sampling is not available:

- The fallback path runs each axis as a sequential local review.
- Sampling availability is recorded in the `PatchReviewReport` and `HarnessConditionSheet`.
- Fallback mode must produce the same `AxisFinding` type as the Sampling path.

### 14.4 `AxisFinding` Model

Required fields:

```text
AxisFinding
  axis
  findings
  evidence_refs
  risk_signals
  confidence
  sampling_used
  reviewer_id
```

### 14.5 Four-Agent Fallback Rules

Rules:

- Neither path should invent evidence not backed by graph, SARIF, or test records.
- LLM output from any axis is soft evidence; it cannot override a deterministic hard failure.
- A blank or low-confidence axis finding is reported as such, not promoted to `unknown`.

---

## 15. `classify_patch_risk` Tool

### 15.1 Purpose

Extract the patch-risk feature vector and return a typed risk classification.

### 15.2 Input

```text
diff
repo?
snapshot_before?
snapshot_after?
sarif_run_before?
sarif_run_after?
run_id?
```

### 15.3 Output

- `PatchRiskResult` with risk class, calibrated probability, ECE bucket, and policy action.
- `PatchRiskFeatureVector` reference.
- Active overrides list.
- Diagnostics for each signal.

### 15.4 Behavior

1. Parse diff.
2. Detect changed symbols.
3. Extract AST diff features.
4. Extract graph context.
5. Compute SARIF delta (if SARIF runs available).
6. Compute test delta (if test evidence available).
7. Check interface compatibility.
8. Check scope and permission audit (from run record if `run_id` provided).
9. Run maintainability oracle.
10. Assemble feature vector.
11. Apply deterministic risk policy.
12. If trained classifier is calibrated for this family: apply classifier, gate by macro-F1/ECE.
13. Return `PatchRiskResult`.

### 15.5 Permissions

- Required mode: read/search.
- Path scope: registered repos and SARIF store.
- Network: none.
- Side effect: writes artefact store for feature vector and result.

### 15.6 Tests

Required tests:

- `classify_patch_risk` returns `safe` for clean fixture.
- Returns `block` for SARIF-new-critical fixture.
- Returns `correct-but-overfit` for test-pass-but-no-reproduction fixture.
- Returns `unknown` when trace-incomplete.
- Returns `block` for scope-violation fixture.

---

## 16. `run_patch_review` Tool

### 16.1 Purpose

Execute the full multi-axis review including DryRUN prediction, four-agent audit, patch-risk classification, SARIF delta, interface compatibility, maintainability gate, scope audit, and operational-review integration.

### 16.2 Input

```text
diff
context?
repos?
policy?
run_id?
sampling_enabled?
task?
```

### 16.3 Output

- `PatchReviewReport` with per-axis findings, evidence, risk class, uncertainty, recommendation.
- `HarnessConditionSheet` reference.
- `RunRecord` reference.
- Operational compliance verdict.

### 16.4 `PatchReviewReport` Model

Required fields:

```text
PatchReviewReport
  report_id
  diff_id
  run_id
  harness_condition_id
  correctness_finding
  security_finding
  performance_finding
  compatibility_finding
  sarif_delta_ref
  test_delta_ref
  interface_compat_result_ref
  dryrun_prediction_ref
  dryrun_mismatches
  scope_audit_result_ref
  maintainability_gate_result_ref
  patch_risk_result_ref
  recommendation
  operational_verdict
  incident_links
  uncertainty
  sampling_used
  fallback_mode
  created_ts
```

`recommendation` values:

- `merge-supporting`
- `review-required`
- `block`
- `unknown`

### 16.5 Workflow

1. Create run record and task.
2. Parse diff and detect changed symbols.
3. Compute DryRUN prediction.
4. Run four-agent audit (Sampling or fallback).
5. Compute SARIF delta.
6. Compute test delta.
7. Check interface compatibility.
8. Run maintainability oracle.
9. Perform scope/permission audit.
10. Classify patch risk.
11. Check operational-review integration (incident links, process compliance).
12. Assemble `PatchReviewReport`.
13. Attach `HarnessConditionSheet`.
14. Store result artefact.
15. Return report.

### 16.6 Permissions

- Required mode: read/search (no writes to repo).
- Path scope: registered repos, SARIF store.
- Network: none.
- Side effect: writes artefact store and operational records.
- Approval: not required.

### 16.7 Tests

Required tests:

- Full review for clean diff fixture returns `merge-supporting`.
- Review with new SARIF critical returns `block`.
- Review with out-of-scope write returns `block`.
- Review with trace-incomplete run returns no auto-merge.
- Four-agent findings included in report.
- `HarnessConditionSheet` attached.
- Sampling mode and fallback mode both produce `PatchReviewReport`.

---

## 17. Operational-Review Integration

### 17.1 Purpose

The patch-review workflow must consume run records from the patch-producing run (if available) to check process compliance. Process violations block auto-merge regardless of functional gate outcomes.

### 17.2 Integration Points

- If `run_id` is provided, load the operational run record and check for trace completeness, budget events, policy violations, and incident links.
- Incident links from the producing run must appear in the `PatchReviewReport`.
- `trace-incomplete` and `budget-exhausted` flags from the run override the merge recommendation to `review-required` or `block`.

### 17.3 `OperationalIntegrationResult` Model

Required fields:

```text
OperationalIntegrationResult
  run_id
  process_verdict
  incident_count
  incident_ids
  trace_complete
  budget_hard_stop
  policy_violation_count
  missing_required_events
  operational_recommendation
```

---

## 18. Private Skill Templates

### 18.1 `audit` Template (Patch Mode)

Entry: `audit(mode="patch", diff="<unified diff>")`.

The template instructs the agent to:

1. Call `run_patch_review(diff)` as a task.
2. Poll to completion.
3. Read each axis finding.
4. Read the SARIF delta and highlight new/disappeared alerts.
5. Read the DryRUN mismatches and flag residual risks.
6. Read the scope audit and flag process violations.
7. Read the maintainability gate and flag structural issues.
8. Summarise the patch-risk class with evidence.
9. State the recommendation: `merge-supporting`, `review-required`, or `block`.
10. List any open incidents that must be resolved before merge.

Rules:

- Template must never claim `merge-supporting` when any deterministic block condition is active.
- Template must never suppress DryRUN mismatches or SARIF alerts.
- Template must include the `HarnessConditionSheet` reference.

### 18.2 `risk-classify` Template

Entry: `risk-classify(diff="<unified diff>", repo?)`.

The template instructs the agent to:

1. Call `classify_patch_risk(diff)`.
2. Report risk class, calibrated probability, and ECE bucket.
3. List active overrides.
4. State which calibration family was used or flag `unknown`.
5. Provide the feature vector summary: AST diff, SARIF delta, graph context, test residue, and vulnerability prior.
6. Give a merge/block recommendation based only on classifier output and active overrides.

Rules:

- Template must never present classifier output as a standalone merge decision.
- Template must flag `unknown` calibration explicitly.
- Template snapshot must be stable.

### 18.3 Template Tests

Required tests:

- Both templates render with all required arguments.
- Template snapshots are stable.
- `audit` template includes contamination of block conditions into recommendation.
- `risk-classify` template includes calibration-family flag.

---

## 19. Test Plan

### 19.1 Model Tests

Required:

- All Phase 11 models round-trip through JSON.
- Missing required fields fail validation.
- Risk class enum values are exhaustive.
- `policy_action` values are typed.

### 19.2 Diff and Symbol Tests

Required:

- Diff parser extracts file paths and hunks.
- Symbol detector maps lines to graph nodes.
- Interface-boundary flag on changed route.
- Generated-file flag on changed stub.
- Stale-index diagnostic.

### 19.3 Feature Extraction Tests

Required:

- AST diff features for each edit operation type.
- Graph context includes two-hop callers/callees.
- SARIF delta: new/disappeared alerts detected.
- Test delta: newly failing tests identified.
- Interface compatibility: breaking and candidate changes.

### 19.4 Gate Tests

Required:

- DryRUN mismatch detected for fixture.
- Scope audit detects out-of-scope write.
- Maintainability gate fires dependency-direction failure.
- Deterministic risk policy fires for each block condition.

### 19.5 Classifier Tests

Required:

- Feature vector assembled from all signals.
- Deterministic policy produces expected risk class for fixtures.
- Calibration-gate not met → deterministic policy used.

### 19.6 Tool Tests

Required:

- `classify_patch_risk` lifecycle.
- `run_patch_review` task lifecycle.
- Sampling path produces `AxisFinding`.
- Fallback path produces `AxisFinding`.
- `HarnessConditionSheet` attached to report.
- Report stored and retrievable.

### 19.7 Template Tests

Required:

- Both templates render.
- Both snapshots stable.
- Block condition in template recommendation.

---

## 20. Work Packages

### P11.1 Diff Parser and Changed-Symbol Detector

Build:

- `DiffRecord` model.
- `ChangedSymbolRecord` model.
- Unified diff parser.
- Symbol-to-graph-node mapper.
- Interface-boundary and generated-file flags.

Deliverables:

- `patch_review/models.py` (partial)
- `patch_review/diff_parser.py`
- `patch_review/symbol_detector.py`
- Parser and detector tests.

Acceptance:

- Changed symbols identified for fixture diff.

### P11.2 AST Diff and Graph Context

Build:

- `ASTDiffFeatures` model.
- Tree-sitter-based AST diff extractor.
- `GraphContextRecord` model.
- Two-hop caller/callee and dataflow extractor.

Deliverables:

- `patch_review/ast_diff.py`
- `patch_review/graph_context.py`
- Tests.

Acceptance:

- AST diff and graph context populated for fixture.

### P11.3 SARIF Delta, Test Delta, Interface Compat

Build:

- `SARIFDelta` wiring from Phase 6.
- `TestDeltaRecord` model.
- `InterfaceCompatibilityResult` model.
- Breaking-change detector.

Deliverables:

- `patch_review/sarif_delta.py`
- `patch_review/test_delta.py`
- `patch_review/interface_compat.py`
- Tests.

Acceptance:

- SARIF delta detects new critical for fixture.
- Interface breaking change detected.

### P11.4 DryRUN Prediction

Build:

- `DryRUNPrediction` model.
- `DryRUNMismatch` model.
- Prediction generator interface (LLM-boundary, null adapter for tests).
- Mismatch detector.

Deliverables:

- `patch_review/dryrun.py`
- DryRUN tests.

Acceptance:

- Prediction and mismatch model populated for fixture.

### P11.5 Scope Audit and Maintainability Gate

Build:

- `ScopeAuditResult` model.
- Permission/trace checker from run record.
- `MaintainabilityGateResult` wiring from Phase 10.
- Block-condition rules.

Deliverables:

- `patch_review/scope_audit.py`
- `patch_review/maintainability_gate.py`
- Tests.

Acceptance:

- Scope violation detected; maintainability failure detected.

### P11.6 Patch-Risk Feature Vector and Classifier

Build:

- `PatchRiskFeatureVector` model.
- Feature assembler from all signals.
- `PatchRiskResult` model.
- Deterministic risk policy.
- Calibration-gate placeholder.

Deliverables:

- `patch_review/risk_features.py`
- `patch_review/risk_classifier.py`
- `patch_review/risk_policy.py`
- Classifier tests with fixture diffs.

Acceptance:

- Risk class correct for all fixture diffs.

### P11.7 Four-Agent Audit and Sampling Integration

Build:

- `AxisFinding` model.
- Sampling integration (stub if client does not support Sampling).
- Fallback sequential path.
- Four-agent orchestrator.

Deliverables:

- `patch_review/four_agent_audit.py`
- `patch_review/sampling_integration.py`
- Tests.

Acceptance:

- Both Sampling and fallback paths produce `AxisFinding` records.

### P11.8 Operational Integration

Build:

- `OperationalIntegrationResult` model.
- Run-record reader for process-compliance verdict.
- Incident-link extractor.

Deliverables:

- `patch_review/operational_integration.py`
- Tests.

Acceptance:

- Trace-incomplete run produces `review-required` or `block` recommendation.

### P11.9 `classify_patch_risk` Tool

Build:

- Tool handler.
- Feature pipeline wiring.
- Artefact store writer.

Deliverables:

- `mcp_server/tools/patch_review.py` (partial)
- Tool tests.

Acceptance:

- Tool returns `PatchRiskResult` for fixture diffs.

### P11.10 `run_patch_review` Tool and Report

Build:

- `PatchReviewReport` model.
- Full workflow orchestration.
- `HarnessConditionSheet` assembly.
- Merge-policy decision.
- Task-capable tool handler.

Deliverables:

- `patch_review/report.py`
- `patch_review/merge_policy.py`
- `mcp_server/tools/patch_review.py` (complete)
- Tool and report tests.

Acceptance:

- Full review for fixture produces typed report with recommendation.

### P11.11 Private Skill Templates

Build:

- `audit.md` template (patch mode).
- `risk_classify.md` template.
- Template snapshot tests.

Deliverables:

- `skills/audit.md`
- `skills/risk_classify.md`
- Template tests.

Acceptance:

- Templates render; snapshots stable.

---

## 21. Suggested Implementation Order

Recommended order:

1. Models: `DiffRecord`, `ChangedSymbolRecord`, `ASTDiffFeatures`, `GraphContextRecord`.
2. Diff parser and symbol detector.
3. AST diff extractor.
4. Graph context extractor.
5. SARIF delta wiring from Phase 6.
6. Test delta model.
7. Interface compatibility model and detector.
8. DryRUN prediction contract and mismatch model.
9. Scope audit.
10. Maintainability gate wiring from Phase 10.
11. Feature vector assembler.
12. Deterministic risk policy.
13. Four-agent audit and Sampling integration.
14. Operational integration.
15. `classify_patch_risk` tool.
16. `run_patch_review` task-capable tool.
17. `audit` and `risk-classify` skill templates.

---

## 22. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 11 |
|---|---|
| Phase 12 - SAST repair | `classify_patch_risk` as the post-repair gate; SARIF delta model |
| Phase 13 - Bug-resolve | `run_patch_review` as the final repair gate; `DryRUNPrediction` contract; `PatchRiskResult` in final report |
| Phase 14 - Implementation-check | `MaintainabilityGateResult` model; `ScopeAuditResult` for clause-level verdicts |
| Phase 15 - Blast radius | `ChangedSymbolRecord` and `InterfaceCompatibilityResult` as blast-radius inputs |
| Phase 16 - Dynamic traces | `DryRUNMismatch` model for trace-vs-prediction comparison |
| Phase 17 - Memory | `PatchRiskResult` and `EvalInstanceResult` for trajectory outcome labelling |
| Phase 18 - Release gates | `HarnessConditionSheet` on every review; calibration-gate enforcement; macro-F1/ECE thresholds |
| Phase 19 - Distribution | `run_patch_review` and `classify_patch_risk` tools; `audit` and `risk-classify` templates |

---

## 23. Exit Criteria Mapping

Source Phase 11 exit criterion:

- `run_patch_review(diff)` returns per-axis findings, evidence, uncertainty, and recommendation.

Concrete acceptance:

- Four-axis findings present in `PatchReviewReport`.
- Evidence references non-null for at least one axis.
- Uncertainty field present.
- Recommendation is one of `merge-supporting`, `review-required`, `block`, or `unknown`.

Source Phase 11 exit criterion:

- New critical SARIF alerts, broken contracts, and failing required tests override a `safe` label.

Concrete acceptance:

- SARIF-new-critical fixture returns `block`.
- Broken-interface fixture returns `block` or `review-required`.
- Failing-required-test fixture returns `block`.

Source Phase 11 exit criterion:

- Out-of-scope writes, unapproved tool use, or missing telemetry override `safe`.

Concrete acceptance:

- Scope-violation fixture returns `block`.
- Trace-incomplete fixture returns no auto-merge recommendation.

Source Phase 11 exit criterion:

- Structural maintainability failures can block merge even when tests pass.

Concrete acceptance:

- Dependency-direction-failure fixture returns `block` or `review-required` when tests pass.

Source Phase 11 exit criterion:

- `unknown` is returned when classifier calibration is missing.

Concrete acceptance:

- Calibration-missing fixture returns `unknown` risk class from classifier path.
- Deterministic policy still applies for override conditions.

Source Phase 11 exit criterion:

- Sampling availability, reviewer roles, fallback mode, classifier calibration family, and deterministic gate outcomes are recorded in the run record.

Concrete acceptance:

- `PatchReviewReport.sampling_used` and `fallback_mode` fields present.
- `harness_condition_id` references a sheet with Sampling status.
- `calibration_family` field in `PatchRiskResult`.

---

## 24. Definition Of Done

Phase 11 is done when:

- Diff parser, changed-symbol detector, AST diff extractor, and graph context extractor are implemented and tested.
- SARIF delta wiring produces new/disappeared/severity-changed findings for fixture.
- DryRUN prediction contract model is defined and populated.
- Scope audit detects out-of-scope writes and missing required events.
- Maintainability gate produces block findings for dependency-direction failure.
- Deterministic risk policy fires correctly for all five fixture diff types.
- `classify_patch_risk` returns typed `PatchRiskResult` with active overrides.
- `run_patch_review` task-capable tool produces `PatchReviewReport` with four-axis findings and recommendation.
- Both Sampling and fallback paths produce `AxisFinding` records.
- Operational-review integration feeds process-compliance verdict into recommendation.
- `HarnessConditionSheet` attached to every `PatchReviewReport`.
- `audit` and `risk-classify` private skill templates render with stable snapshots.
- All deterministic block conditions override `safe` unconditionally.
- `unknown` returned when calibration data is missing.

---

## 25. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `safe` label used without deterministic gates | Risky patch approved | Enforce: `safe` requires all deterministic gate checks to pass, not only classifier output |
| Trained classifier deployed before calibration threshold met | Calibration gate causes false merge-blocks or false approvals | Gate classifier-driven merge decisions on macro-F1 ≥0.75 and ECE ≤0.10 per language/rule family; use deterministic policy until met |
| SARIF unavailable for the patch's before/after state | Critical new alerts missed | Log SARIF absence as diagnostic; treat missing SARIF as `unknown` not `clean` |
| Sampling unavailable but tests assume Sampling | Tests pass but production fallback path is broken | Require both Sampling and fallback paths to produce equivalent `AxisFinding` types; test both |
| DryRUN mismatch suppressed in report | Residual risks not communicated to reviewer | Template and report model require all mismatches to be listed; no mismatch filtering by default |
| Operational run record not linked | Process-compliance cannot be checked | Log absence of run_id as diagnostic; `trace-incomplete` verdict when run record unavailable |
| Four-agent findings override deterministic block | LLM output overrides hard evidence | Deterministic overrides are applied unconditionally before four-agent findings are combined |
| Maintainability gate too aggressive | Every refactor blocks merge | Single property failures (except dependency direction) are `review-required` not `block`; threshold tunable |

---

## 26. Phase 11 Completion Report Template

When Phase 11 implementation is complete, report:

```text
Phase 11 completion report

Implemented:
- Diff parser and changed-symbol detector:
- AST diff feature extractor:
- Graph context extractor:
- SARIF delta integration:
- Test delta model:
- Interface compatibility check:
- DryRUN prediction contract:
- Scope and permission audit:
- Maintainability gate:
- Patch-risk feature vector:
- Deterministic risk policy:
- Four-agent audit (Sampling + fallback):
- Operational-review integration:
- classify_patch_risk tool:
- run_patch_review task-capable tool:
- audit skill template (patch mode):
- risk-classify skill template:

Verification:
- Diff and symbol tests:
- Feature extraction tests:
- Gate tests:
- Classifier tests:
- Tool tests:
- Template snapshot tests:
- Block-condition override tests:

Exit criteria:
- run_patch_review returns per-axis findings:
- Critical SARIF/broken contract/failing test override safe:
- Out-of-scope writes/missing telemetry override safe:
- Maintainability failures can block:
- unknown on missing calibration:
- Sampling/fallback/calibration recorded in run record:

Known limitations:
-

Follow-up for Phase 12:
-
```

---

## 27. Minimal First Slice Within Phase 11

If Phase 11 needs to be split further, implement this first:

1. `DiffRecord` and `ChangedSymbolRecord` models.
2. Unified diff parser.
3. Symbol-to-graph-node mapper.
4. SARIF delta wiring.
5. `ScopeAuditResult` model.
6. Deterministic risk policy (five block rules).
7. `classify_patch_risk` tool.
8. `PatchReviewReport` model.
9. `run_patch_review` task-capable tool in single-axis mode.
10. `audit` skill template stub.

This minimal slice makes patches reviewable by MCP clients, enforces deterministic block conditions, and unblocks Phase 12 (SAST repair) which needs `classify_patch_risk` as its post-repair gate.
