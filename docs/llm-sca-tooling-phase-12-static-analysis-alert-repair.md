# LLM-SCA Tooling Phase 12 Implementation Plan: Static-Analysis Alert Repair

> Date: 2026-05-09
> Repository name: `evidence-sca`
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 12 - Static-Analysis Alert Repair
> Primary objective: repair SARIF/SAST alerts using analyser evidence — alert binding, PredicateFix-style predicate-example retrieval, repair context building, patch generation interface, SARIF delta verification, `run_sast_repair` tool, `get_predicate_examples` tool, and the private `sast-repair` skill template.

---

## 1. Phase Summary

Phase 12 is the first repair-facing phase of `evidence-sca`. Phases 1-11 built the index, SARIF layer, fault localisation, evaluation baseline, and the patch-review safety gates. Phase 12 adds the first automated repair capability: fixing SAST/SARIF alerts by combining analyser evidence with the PredicateFix-style predicate-example retrieval pattern, then verifying the fix with SARIF delta, build, and test rerun.

The central rule for this phase is:

```text
A SAST alert is not fixed until the original alert disappears from SARIF output
after the patch is applied and the analyser re-runs on the patched code.
New higher-severity alerts block success unconditionally.
Confirmed false positives may produce a reviewed suppression or an offline
rule-evolution candidate — never an unreviewed analyser-rule mutation.
Rule evolution remains an offline workflow until it demonstrates ≥10 pp
false-positive reduction at k=5 with zero true-positive loss.
```

Phase 12 should implement:

- Alert binding to graph nodes.
- Rule/predicate metadata extraction.
- Developer-facing alert explanation generator.
- Alert classification: likely true positive, likely false positive, unknown.
- Predicate-example retrieval interface (PredicateFix pattern).
- Clean corpus adapter.
- Repair prompt context builder.
- Patch generation interface (LLM boundary).
- Suppression proposal path for confirmed false positives.
- Patch application sandbox.
- Analyser rerun integration.
- SARIF delta verification.
- Build and test rerun integration.
- Remaining-risk notes.
- Optional offline rule-refinement workflow stub.
- `run_sast_repair` and `get_predicate_examples` tools.
- Private `sast-repair` skill template.

### Architecture Coverage

Phase 12 covers:

- F7 static-analysis alert repair.
- `run_sast_repair` tool.
- `get_predicate_examples` tool.
- Optional offline `evolve_static_rules` (stub only in Phase 12).
- Private `sast-repair` skill template.

Tools in this phase:

- `run_sast_repair`
- `get_predicate_examples`
- `evolve_static_rules` (stub)

Private skill template in this phase:

- `sast-repair`

### Inherited Paper Anchors

Use these anchors in Phase 12 issues, ADRs, and repair reports:

- `predicatefix`
- `codecureagent`
- `securefixagent`
- `nullrepair`
- `codeql-rule-multiagent`
- `agent-coevo`
- `llm4cve`
- `logiceval`

## Technology Stack

This phase uses the following libraries from `llm-sca-tooling-tech-stack.md`:

| Library/Tool | PyPI package | Version | Role in this phase |
|---|---|---|---|
| Python | — | 3.12+ | Runtime |
| uv | — | latest | Environment and dependency management |
| Pydantic v2 | `pydantic` | >=2.0 | `AlertBinding`, `PredicateMetadata`, `PredicateExampleRecord`, `RepairContext`, `SASTPatch`, `SASTRepairReport` schemas; `extra="forbid"` on all models |
| orjson | `orjson` | >=3.10 | SARIF result parsing (alerts can be large), patch payload serialisation, all JSON I/O |
| FastMCP + FastAPI | `fastmcp`, `fastapi` | >=2.0, >=0.115 | `run_sast_repair` and `get_predicate_examples` MCP tool handlers |
| httpx | `httpx` | >=0.27 | `PolicyAwareHTTPClient` wrapping for HC5 |
| pytest + pytest-asyncio | `pytest`, `pytest-asyncio` | >=8.0, >=0.23 | SAST repair tests; `asyncio_mode="auto"` |

- All subprocess calls (Semgrep/Bandit re-run for SARIF delta verification) use `asyncio.create_subprocess_exec`; `subprocess.run` is forbidden.
- All tool handlers and workflow functions are `async def`.
- SARIF JSON is parsed via the custom normaliser using orjson; no external SARIF library is used.
- Rich is restricted to the CLI layer; all other modules use `logging`.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 12 depends on:

- Phase 1 schemas:
  - `SARIFAlert`, `SARIFRun`, and `SARIFDelta` models
  - `ContractArtifact` model
  - `Patch` and `RiskFinding` models
  - `RunRecord` and `RunEvent` models
- Phase 2 stores:
  - graph store with symbol and file nodes
  - SARIF run store from Phase 6
  - operational store
  - artefact registry
- Phase 5 language backends:
  - AST-based symbol index for predicate matching
- Phase 6 SARIF layer:
  - alert-to-graph binding
  - SARIF delta utility
  - `run_static_analysis` for analyser rerun
- Phase 7 interface plugins:
  - interface contract records for contracts broken/fixed by the repair
- Phase 9 fault localisation:
  - alert location as a ranked suspect input
- Phase 10 evaluation harness:
  - `EvalRun` model
  - `HarnessConditionSheet` model
- Phase 11 patch review:
  - `classify_patch_risk` as the post-repair gate
  - `PatchRiskResult` and `PatchReviewReport` in repair output

### Phase Outputs

Phase 12 should produce:

- `AlertBinding` model.
- `AlertClassification` model with true-positive/false-positive/unknown result.
- `PredicateMetadata` model.
- `PredicateExampleRecord` model.
- `CleanCorpusAdapter` interface and local corpus adapter.
- `RepairContext` model.
- `SASTPatch` model.
- `SuppressionProposal` model.
- `SandboxResult` model.
- `AnalyserRerunResult` model.
- `SARIFDeltaVerificationResult` model.
- `RemainingRiskNote` model.
- `SASTRepairReport` model.
- `run_sast_repair` tool handler.
- `get_predicate_examples` tool handler.
- `evolve_static_rules` stub.
- `sast-repair` skill template.
- SAST repair tests.

### Non-Goals

Do not implement these in Phase 12:

- Full end-to-end bug-resolve workflow (Phase 13).
- Implementation-check workflow (Phase 14).
- Blast-radius service (Phase 15).
- Dynamic trace capture (Phase 16).
- Trajectory memory (Phase 17).
- Trained ML classifier for alert classification beyond rule-based confidence.
- Full offline rule-evolution deployment (only a non-operational stub).
- Automated vulnerability disclosure or exploit generation.
- Repair for alert types not yet covered by Phase 6 SARIF adapters.

---

## 3. Recommended File Layout

Assuming package name `evidence_sca`:

```text
src/evidence_sca/
  sast_repair/
    __init__.py
    models.py
    alert_binding.py
    alert_classification.py
    predicate_metadata.py
    predicate_examples.py
    corpus_adapter.py
    repair_context.py
    patch_generator.py
    suppression.py
    sandbox.py
    analyser_rerun.py
    sarif_delta_verifier.py
    build_test_runner.py
    remaining_risk.py
    report.py
    rule_evolution.py

  mcp_server/
    tools/
      sast_repair.py

  skills/
    sast_repair.md

tests/
  sast_repair/
    fixtures/
      alerts/
        nullderef_alert.json
        injection_alert.json
        false_positive_alert.json
        unknown_alert.json
      sarif_before/
        nullderef_run.sarif
        injection_run.sarif
      sarif_after/
        nullderef_fixed.sarif
        injection_fixed.sarif
        injection_new_critical.sarif
      corpus/
        nullderef_examples.json
        injection_examples.json
    test_alert_binding.py
    test_alert_classification.py
    test_predicate_metadata.py
    test_predicate_examples.py
    test_corpus_adapter.py
    test_repair_context.py
    test_patch_generator.py
    test_suppression.py
    test_sandbox.py
    test_analyser_rerun.py
    test_sarif_delta_verifier.py
    test_build_test_runner.py
    test_remaining_risk.py
    test_report.py
    test_rule_evolution.py
    test_run_sast_repair.py
    test_get_predicate_examples.py
    test_sast_repair_template.py
```

---

## 4. Alert Binding to Graph Nodes

### 4.1 Purpose

Alert binding maps a SARIF alert from Phase 6 to one or more graph nodes (symbols, files, or spans) so the repair context can be assembled from structured graph evidence rather than raw file text.

### 4.2 `AlertBinding` Model

Required fields:

```text
AlertBinding
  alert_id
  sarif_alert_ref
  rule_id
  rule_family
  cwe_ids
  file_node_id
  file_path
  span
  primary_symbol_node_ids
  related_symbol_node_ids
  dataflow_path_nodes
  cross_file_nodes
  graph_snapshot_id
  confidence
  diagnostics
```

### 4.3 Binding Algorithm

The binding algorithm should:

1. Look up the alert location in Phase 6's SARIF run store.
2. Map the file path and span to a graph `file` node.
3. Resolve the primary symbol(s) at the alert span using the Phase 5 AST index.
4. Extract the dataflow path from the alert if the rule reports flows.
5. Map flow nodes to graph symbols where possible.
6. Produce `confidence: parser` when the file node and symbol are matched via AST; `confidence: analyser` when only the file node is matched; `confidence: heuristic` when only the file path matches.
7. Produce a diagnostic when graph snapshot is stale relative to the SARIF run.

### 4.4 Rules

Rules:

- Missing symbol binding is not a failure; record `confidence: heuristic` and proceed.
- Stale graph snapshot must appear in the binding diagnostics.
- Alerts with empty `locations` array are not silently skipped; they produce an explicit `no_location` diagnostic.

### 4.5 Tests

Required tests:

- Alert bound to graph node for fixture nullderef alert.
- Alert bound to file node only when symbol resolution fails.
- Stale snapshot diagnostic present.
- No-location alert produces `no_location` diagnostic.

---

## 5. Rule and Predicate Metadata Extraction

### 5.1 Purpose

Rule metadata tells the repair context what the analyser is checking for and why the alert fired. Predicate metadata is the structured form of this knowledge, following the PredicateFix pattern.

### 5.2 `PredicateMetadata` Model

Required fields:

```text
PredicateMetadata
  rule_id
  rule_family
  predicate_text
  negated_predicate_text
  cwe_ids
  severity
  description
  fix_guidance
  known_false_positive_patterns
  available_examples
  source
  confidence
```

### 5.3 Metadata Sources

Sources in priority order:

1. SARIF rule metadata from the tool's `run.tool.driver.rules` array.
2. Phase 6 SARIF adapter's rule-family normalization table.
3. Hardcoded rule database for common Semgrep/Bandit/CodeQL rule IDs.
4. `unknown` when no source matches.

### 5.4 Predicate Negation

Following the PredicateFix pattern, the `negated_predicate_text` is the logical complement of the firing predicate. It describes code that does not trigger the alert — i.e., the pattern of correct code that the LLM should generate.

Rules:

- Negated predicate should be extracted from the analyser's rule definition where available.
- When not available, set `negated_predicate_text: null` and log diagnostic.

---

## 6. Alert Classification

### 6.1 Purpose

Before attempting repair, the alert should be classified as likely true positive, likely false positive, or unknown. Classification uses static evidence from the graph, rule metadata, and historical project signals — not LLM judgment.

### 6.2 `AlertClassification` Model

Required fields:

```text
AlertClassification
  alert_id
  binding_ref
  classification
  tp_evidence
  fp_evidence
  confidence
  calibrated
  suppression_history
  diagnostics
```

`classification` values:

- `likely_true_positive`
- `likely_false_positive`
- `unknown`

### 6.3 Classification Evidence

True-positive evidence sources:

- Dataflow path is confirmed in the graph (dataflow edges present, not just heuristic).
- Symbol is known to be involved in security-sensitive operations.
- Same alert pattern triggered on similar code elsewhere in the project.
- No suppression comment or annotation in the source file.

False-positive evidence sources:

- Dataflow path is not reachable in the graph (dataflow edge absent with `confidence: parser`).
- Rule is known to have high false-positive rate for this code pattern (from historical project suppression data).
- Symbol is a test-only construct not reachable from production code paths.
- Alert was previously suppressed with a reviewed reason.

### 6.4 Rules

Rules:

- `likely_false_positive` with `confidence: parser` evidence can propose a suppression.
- `likely_false_positive` with only `heuristic` evidence cannot automatically suppress; produce a candidate for human review.
- `unknown` classification proceeds to repair with lower priority and explicit uncertainty note.
- The classification is non-binding: a `likely_false_positive` classification can still be repaired if the developer chooses.

---

## 7. Predicate-Example Retrieval

### 7.1 Purpose

Following the PredicateFix pattern, predicate-example retrieval retrieves fix-knowledge from the analyser's own logic by negating the firing predicate and running the analyser against a clean reference corpus. Code snippets where the negated predicate fires contain the pattern the LLM needs to produce a correct repair. This gives 27-69% more correct repairs than embedding-similarity RAG.

### 7.2 `PredicateExampleRecord` Model

Required fields:

```text
PredicateExampleRecord
  rule_id
  negated_predicate
  corpus_id
  example_id
  file_path
  span
  code_snippet
  snippet_language
  confidence
  retrieval_method
```

`retrieval_method` values:

- `predicate_negation`: negated predicate fired in corpus — strongest signal.
- `rule_family_match`: same rule family in corpus, predicate negation unavailable.
- `embedding_similarity`: semantic RAG fallback — weakest signal.

### 7.3 `CleanCorpusAdapter` Interface

Recommended interface:

```text
CleanCorpusAdapter
  corpus_id
  corpus_version
  supports_predicate_query()
  query_by_predicate(rule_id, negated_predicate) -> list[PredicateExampleRecord]
  query_by_rule_family(rule_family) -> list[PredicateExampleRecord]
  query_by_embedding(embedding, k) -> list[PredicateExampleRecord]
```

### 7.4 Local Fixture Corpus Adapter

The `LocalFixtureCorpusAdapter` loads pre-curated examples from `tests/sast_repair/fixtures/corpus/`. It supports:

- `query_by_predicate`: loads examples matching the rule ID.
- `query_by_rule_family`: loads examples by rule family prefix.
- No embedding query (returns empty list with diagnostic).

### 7.5 `get_predicate_examples` Tool

Purpose: retrieve predicate-derived fix-knowledge examples for a SARIF alert.

Input:

```text
predicate_id
rule_id?
corpus?
k?
```

Output:

- List of `PredicateExampleRecord` objects.
- Retrieval method used for each example.
- Corpus freshness metadata.
- Diagnostic if predicate negation was unavailable.

Rules:

- Prefer `predicate_negation` method.
- Fall back to `rule_family_match` if predicate negation is unavailable.
- Fall back to `embedding_similarity` only as last resort; flag in diagnostic.
- Return at most `k` examples (default 5).
- Do not include examples from the repo being repaired (corpus must be external to the target repo).

Permissions:

- Required mode: read/search.
- Path scope: workspace and corpus store.
- Network: none.
- Side effect: none.

Tests:

- Returns examples for fixture rule ID.
- Falls back to rule-family match when predicate unavailable.
- Does not include examples from the target repo.
- Corpus freshness metadata present.

---

## 8. Repair Context Builder

### 8.1 Purpose

The repair context assembles everything the patch generator needs: the graph slice around the alert, the alert explanation, the predicate examples, the interface contract (if relevant), and the DryRUN prediction template.

### 8.2 `RepairContext` Model

Required fields:

```text
RepairContext
  alert_id
  binding_ref
  classification_ref
  graph_slice_ref
  alert_explanation
  predicate_examples_ref
  interface_contracts_ref
  snapshot_id
  language
  file_path
  span
  context_tokens_estimate
  budget_remaining
  provenance
```

### 8.3 Alert Explanation

The alert explanation is a brief, developer-facing description of:

- What the alert means.
- Why the code triggered it.
- What a correct fix looks like according to the predicate examples.

The explanation is generated by the repair context builder from the `PredicateMetadata` and `PredicateExampleRecord` objects, without calling an LLM. When metadata is sparse, the explanation is a short template fill: rule name, CWE, and fix-knowledge source.

### 8.4 Context Budget

Rules:

- The repair context must fit within the configured context budget minus the LLM-synthesised patch placeholder.
- If the graph slice plus predicate examples exceed budget, prefer examples over graph slice (examples carry more fix-knowledge per token).
- Budget exhaustion must be recorded as a budget event and logged in the repair run record.

---

## 9. Patch Generator Interface

### 9.1 Purpose

The patch generator interface is the LLM boundary for SAST repair. It takes a `RepairContext` and returns a `SASTPatch`. It is abstract in Phase 12 with a null adapter for testing.

### 9.2 `PatchGeneratorInterface` Abstract Interface

Recommended interface:

```text
PatchGeneratorInterface
  generate(context: RepairContext) -> SASTPatch
  model_id
  version
```

### 9.3 `SASTPatch` Model

Required fields:

```text
SASTPatch
  alert_id
  diff_text
  diff_format
  changed_files
  generator_model
  generation_method
  confidence
  certificate_text
  reasoning_chain
  dryrun_prediction_ref
  provenance
```

`generation_method` values:

- `predicate_repair`: patch generated from predicate-example context — highest quality.
- `graph_slice_repair`: patch generated from graph slice context.
- `null_repair`: null adapter output for testing.

### 9.4 Null Adapter

The null adapter returns:

- A deterministic empty diff for smoke testing.
- `generation_method: null_repair`.
- `confidence: unknown`.
- Full provenance metadata populated.

The null adapter allows the full repair pipeline (context building → patch → sandbox → analyser rerun → SARIF delta → risk gate) to be tested without LLM calls.

---

## 10. Suppression Proposal Path

### 10.1 Purpose

Confirmed false positives should not be repaired with dummy patches. The suppression path generates a structured suppression proposal for human review instead.

### 10.2 `SuppressionProposal` Model

Required fields:

```text
SuppressionProposal
  alert_id
  rule_id
  classification_ref
  suppression_kind
  annotation_text
  suppression_scope
  reviewer_required
  offline_rule_evolution_candidate
  provenance
```

`suppression_kind` values:

- `inline_comment`: add a suppression comment at the alert location.
- `baseline_entry`: add the alert to an analyser baseline file.
- `rule_evolution_candidate`: flag for offline rule refinement.

### 10.3 Rules

Rules:

- A suppression proposal is only generated when `alert_classification: likely_false_positive` with `confidence >= analyser`.
- `reviewer_required: true` for all suppression proposals in Phase 12.
- Inline suppression comments must include the rule ID and a human-readable reason.
- Baseline entries must reference the current git SHA.
- An unreviewed analyser-rule mutation must never be applied automatically.

---

## 11. Patch Application Sandbox

### 11.1 Purpose

The patch must be applied to a sandbox copy of the repository before running the analyser. Sandbox application prevents uncommitted changes to the working tree during the repair loop.

### 11.2 `SandboxResult` Model

Required fields:

```text
SandboxResult
  alert_id
  sandbox_path
  patch_applied
  apply_error
  sandbox_snapshot_id
  cleanup_policy
```

### 11.3 Sandbox Rules

Rules:

- The sandbox is a temporary workspace copy, not the registered repo root.
- The sandbox must be cleaned up after the repair loop completes, regardless of outcome.
- Sandbox operations must not be listed in the permission policy as writes to the registered repo.
- Sandbox path must be within the workspace allowlist (HC2).

---

## 12. Analyser Rerun

### 12.1 Purpose

After applying the patch in the sandbox, the analyser must be re-run on the affected files to produce the after-repair SARIF output for the delta check.

### 12.2 `AnalyserRerunResult` Model

Required fields:

```text
AnalyserRerunResult
  alert_id
  sandbox_snapshot_id
  analyser_id
  analyser_version
  rerun_status
  sarif_run_id_after
  rerun_diagnostic
  wall_ms
```

### 12.3 Rerun Rules

Rules:

- Use Phase 6's `run_static_analysis` logic to run the analyser in the sandbox scope.
- Only re-run the analyser on the changed files, not the full repo, when the analyser supports file-scoped analysis.
- If the analyser requires a full-repo run, log a diagnostic and proceed.
- Analyser tool version must be recorded in the `AnalyserRerunResult` and the `HarnessConditionSheet`.

---

## 13. SARIF Delta Verification

### 13.1 Purpose

The delta check is the primary success criterion for SAST repair. The original alert must disappear; new higher-severity alerts must not appear.

### 13.2 `SARIFDeltaVerificationResult` Model

Required fields:

```text
SARIFDeltaVerificationResult
  alert_id
  sarif_run_before_id
  sarif_run_after_id
  original_alert_gone
  original_alert_remains
  new_alerts
  new_critical_or_error_alerts
  severity_regressions
  net_alert_delta
  success
  block_reason
```

### 13.3 Success and Block Conditions

Success condition:

- `original_alert_gone: true` AND `new_critical_or_error_alerts: []`.

Block conditions (override success):

- `original_alert_remains: true` → repair failed; do not report as fixed.
- `new_critical_or_error_alerts: non-empty` → repair introduced new issues; block success.
- `severity_regressions: non-empty` → any alert increased in severity; report as partial success with remaining risk.

---

## 14. Build and Test Rerun Integration

### 14.1 Purpose

SARIF delta alone is necessary but not sufficient. The repaired code must also build and pass existing tests.

### 14.2 `BuildTestResult` Model

Required fields:

```text
BuildTestResult
  alert_id
  sandbox_snapshot_id
  build_status
  test_run_status
  newly_failing_tests
  newly_passing_tests
  flaky_tests_detected
  reproduction_test_executed
  reproduction_test_result
  wall_ms
  diagnostics
```

### 14.3 Rerun Scope

Rules:

- Run only tests that exercise the changed files (from Phase 10's test coverage data where available).
- If coverage data is unavailable, run the full test suite and log the diagnostic.
- Flaky tests must be flagged using Phase 10's flaky-test record.
- A newly failing test blocks the repair success verdict.

---

## 15. Remaining-Risk Notes

### 15.1 Purpose

When the original alert disappears but root-cause behaviour is not fully verified, the repair must include explicit remaining-risk notes.

### 15.2 `RemainingRiskNote` Model

Required fields:

```text
RemainingRiskNote
  alert_id
  risk_level
  risk_description
  verification_method_used
  unverified_paths
  recommended_followup
```

`risk_level` values:

- `none`: full verification passed, no remaining risk identified.
- `low`: minor unverified edge cases; no security-sensitive paths.
- `medium`: some execution paths not covered by tests or graph evidence.
- `high`: security-sensitive paths not fully verified; recommend dynamic trace or manual review.

### 15.3 When Remaining-Risk Notes Are Required

Remaining-risk notes are required when:

- The repair fixes a vulnerability-class alert but PoC+ tests are not available.
- Graph dataflow coverage of the repaired path is partial.
- The only verification is that the SARIF alert disappeared (no test or PoC+ confirmation).

---

## 16. `SASTRepairReport` Model

### 16.1 Required Fields

```text
SASTRepairReport
  report_id
  alert_id
  run_id
  harness_condition_id
  alert_binding_ref
  alert_classification_ref
  predicate_examples_ref
  repair_context_ref
  patch_ref
  suppression_proposal_ref
  sarif_delta_ref
  build_test_result_ref
  patch_risk_result_ref
  remaining_risk_note_ref
  success
  verdict
  recommendation
  created_ts
```

`verdict` values:

- `alert_fixed`: original alert gone, no new critical alerts, tests pass.
- `alert_fixed_with_risk`: alert gone, tests pass, but remaining risk notes non-empty.
- `partially_fixed`: alert severity reduced but not eliminated.
- `repair_failed`: alert remains after patch.
- `repair_blocked`: new critical alert introduced.
- `false_positive_suppressed`: confirmed false positive; suppression proposal generated.
- `unknown`: insufficient evidence to determine outcome.

---

## 17. `run_sast_repair` Tool

### 17.1 Purpose

Execute the full SAST repair loop for a single alert: bind → classify → retrieve examples → build context → generate patch → apply in sandbox → rerun analyser → verify SARIF delta → check patch risk → assemble report.

### 17.2 Input

```text
alert_id
repo?
corpus?
generate_patch?
null_mode?
task?
```

### 17.3 Output

- `TaskCreateResult` for the repair task.
- On completion: `SASTRepairReport` reference.

### 17.4 Workflow

1. Create run record and task.
2. Bind alert to graph nodes.
3. Classify alert.
4. If `likely_false_positive` with high confidence: generate suppression proposal; skip repair unless `generate_patch: true`.
5. Extract predicate metadata.
6. Retrieve predicate examples via `get_predicate_examples`.
7. Build repair context.
8. Generate patch (or null-mode patch).
9. Apply patch in sandbox.
10. Re-run analyser in sandbox.
11. Compute SARIF delta.
12. Run build and tests.
13. Classify patch risk via Phase 11's `classify_patch_risk`.
14. Generate remaining-risk notes.
15. Assemble `SASTRepairReport`.
16. Attach `HarnessConditionSheet`.
17. Store result artefact.
18. Return report.

### 17.5 Permissions

- Required mode: read/search for binding and context; execute for analyser rerun and build/test.
- Path scope: registered repo root and sandbox workspace only.
- Network: none.
- Side effect: writes sandbox workspace, artefact store, and operational records.
- Approval: sandbox execution requires execute mode.

### 17.6 Tests

Required tests:

- Full repair for nullderef fixture: alert gone, report `alert_fixed`.
- Repair for injection fixture with new critical: report `repair_blocked`.
- False-positive fixture: suppression proposal generated, repair skipped.
- Null-mode run completes pipeline without LLM.
- `HarnessConditionSheet` attached to report.

---

## 18. Offline Rule-Refinement Stub

### 18.1 Purpose

The `evolve_static_rules` operation is an offline workflow that improves false-positive rates for analyser rules. It must not run inside ordinary SAST repair.

### 18.2 `evolve_static_rules` Stub

In Phase 12, `evolve_static_rules` is a stub that:

- Accepts `sarif_deltas` and `ruleset` arguments.
- Returns a `not_implemented_in_phase_12` status.
- Records that the tool exists but is gated on a quality threshold.

### 18.3 Promotion Gate

When implemented in a later phase:

- Must demonstrate ≥10 pp false-positive reduction at k=5 on the validation set.
- Must have zero true-positive loss.
- Must produce a reviewable candidate, not an automatic rule change.
- Must only update rules in a separate offline rule workspace, never directly in the production ruleset.

---

## 19. Private `sast-repair` Skill Template

### 19.1 Purpose

The `sast-repair` template is the session-level orchestration plan for repairing a SAST alert. It instructs the agent to follow the PredicateFix loop: alert → predicate context → predicate examples → graph slice → patch → coevolved checks → static analysis/build/test re-check.

### 19.2 Template Arguments

```text
alert_id
repo?
```

### 19.3 Template Structure

The template instructs the agent to:

1. Call `get_predicate_examples(alert_id)` to fetch fix-knowledge.
2. Call `run_sast_repair(alert_id)` as a task.
3. Poll to completion.
4. Read the `SASTRepairReport`.
5. Report: alert classification, predicate examples used, SARIF delta, build/test result, patch-risk class.
6. If `alert_fixed`: state the fix clearly; include remaining-risk notes if non-empty.
7. If `alert_fixed_with_risk`: state the fix with explicit remaining-risk callout.
8. If `repair_blocked`: state the new alert(s) introduced and flag for review.
9. If `false_positive_suppressed`: present the suppression proposal for reviewer decision.
10. Include the `HarnessConditionSheet` reference.
11. Include the `run_id` for operational review.

### 19.4 Rules

Rules:

- Template must not claim `alert_fixed` when `original_alert_remains: true`.
- Template must not suppress new critical alerts from the report.
- Template must flag `reviewer_required` for suppression proposals.
- Template must include remaining-risk notes verbatim.
- Template snapshot must be stable.

---

## 20. Test Plan

### 20.1 Model Tests

Required:

- All Phase 12 models round-trip through JSON.
- Missing required fields fail validation.
- `AlertClassification.classification` enum is exhaustive.
- `SASTRepairReport.verdict` enum is exhaustive.

### 20.2 Binding Tests

Required:

- Alert bound to symbol for nullderef fixture.
- Alert bound to file only when symbol unavailable.
- Stale snapshot produces diagnostic.
- Empty location produces `no_location` diagnostic.

### 20.3 Classification Tests

Required:

- `likely_true_positive` for dataflow-confirmed fixture.
- `likely_false_positive` for test-only-symbol fixture.
- `unknown` for sparse-evidence fixture.

### 20.4 Predicate Example Tests

Required:

- Examples returned for fixture rule ID (predicate negation method).
- Fall-back to rule-family match when predicate unavailable.
- Examples from target repo excluded.

### 20.5 Repair Loop Tests

Required:

- Context builder populates graph slice and examples.
- Null adapter returns deterministic output.
- Sandbox applies patch without touching registered repo.
- Analyser rerun produces after-repair SARIF.
- SARIF delta: original alert gone = success.
- SARIF delta: original alert remains = `repair_failed`.
- SARIF delta: new critical = `repair_blocked`.
- Build/test rerun: newly failing test blocks success.
- Remaining-risk notes required for vulnerability-class alert without PoC+.

### 20.6 Tool Tests

Required:

- `get_predicate_examples` lifecycle.
- `run_sast_repair` task lifecycle (null mode).
- `run_sast_repair` for false-positive fixture.
- `evolve_static_rules` stub returns `not_implemented`.
- `HarnessConditionSheet` attached to every report.

### 20.7 Template Tests

Required:

- Template renders with all required arguments.
- Template snapshot stable.
- `remaining_risk` callout present in template structure.

---

## 21. Work Packages

### P12.1 Alert Binding and Classification

Build:

- `AlertBinding` model and binding algorithm.
- `AlertClassification` model and classification evidence logic.
- False-positive and true-positive detectors.

Deliverables:

- `sast_repair/models.py` (partial)
- `sast_repair/alert_binding.py`
- `sast_repair/alert_classification.py`
- Tests.

Acceptance:

- Alert bound to graph node for nullderef fixture; classified correctly.

### P12.2 Predicate Metadata and Examples

Build:

- `PredicateMetadata` model and extraction logic.
- `PredicateExampleRecord` model.
- `CleanCorpusAdapter` interface.
- `LocalFixtureCorpusAdapter`.
- `get_predicate_examples` tool handler.

Deliverables:

- `sast_repair/predicate_metadata.py`
- `sast_repair/predicate_examples.py`
- `sast_repair/corpus_adapter.py`
- Fixture corpus examples.
- Tool handler.
- Tests.

Acceptance:

- Examples returned for fixture rule ID; tool returns typed list.

### P12.3 Repair Context Builder

Build:

- `RepairContext` model.
- Graph slice assembly from Phase 9/4.
- Alert explanation generator.
- Budget-aware context assembler.

Deliverables:

- `sast_repair/repair_context.py`
- Tests.

Acceptance:

- Context populated for nullderef fixture within budget.

### P12.4 Patch Generator and Null Adapter

Build:

- `PatchGeneratorInterface` abstract interface.
- `SASTPatch` model.
- Null adapter.
- LLM boundary documentation stub.

Deliverables:

- `sast_repair/patch_generator.py`
- Tests.

Acceptance:

- Null adapter returns deterministic `SASTPatch`; interface is abstract.

### P12.5 Suppression Proposal Path

Build:

- `SuppressionProposal` model.
- Suppression generator from false-positive classification.

Deliverables:

- `sast_repair/suppression.py`
- Tests.

Acceptance:

- Suppression proposal generated for false-positive fixture with `reviewer_required: true`.

### P12.6 Sandbox and Analyser Rerun

Build:

- `SandboxResult` model.
- Sandbox workspace manager.
- `AnalyserRerunResult` model.
- Rerun integration with Phase 6 `run_static_analysis`.

Deliverables:

- `sast_repair/sandbox.py`
- `sast_repair/analyser_rerun.py`
- Tests.

Acceptance:

- Sandbox applies patch; analyser re-runs on sandbox; result stored.

### P12.7 SARIF Delta Verification

Build:

- `SARIFDeltaVerificationResult` model.
- Delta check logic using Phase 6 delta utility.
- Success/block condition evaluator.

Deliverables:

- `sast_repair/sarif_delta_verifier.py`
- Tests.

Acceptance:

- Delta correctly identifies fixed/remaining/new-critical for fixture cases.

### P12.8 Build/Test Rerun and Remaining Risk

Build:

- `BuildTestResult` model.
- Test runner integration (scoped to changed files).
- `RemainingRiskNote` model.
- Risk note generator.

Deliverables:

- `sast_repair/build_test_runner.py`
- `sast_repair/remaining_risk.py`
- Tests.

Acceptance:

- Newly failing test blocks success; remaining risk note for vulnerability-class alert.

### P12.9 `run_sast_repair` Tool and Report

Build:

- `SASTRepairReport` model.
- Full workflow orchestration.
- `HarnessConditionSheet` assembly.
- Task-capable tool handler.

Deliverables:

- `sast_repair/report.py`
- `mcp_server/tools/sast_repair.py`
- Full tool tests.

Acceptance:

- MCP client can launch repair, poll task, read report.

### P12.10 Rule-Evolution Stub and `sast-repair` Template

Build:

- `evolve_static_rules` stub.
- `sast-repair.md` skill template.
- Template snapshot test.

Deliverables:

- `sast_repair/rule_evolution.py`
- `skills/sast_repair.md`
- Template tests.

Acceptance:

- Stub returns `not_implemented`; template renders; snapshot stable.

---

## 22. Suggested Implementation Order

Recommended order:

1. Alert binding model and algorithm.
2. Alert classification model and evidence logic.
3. Predicate metadata extraction.
4. Predicate example model and `CleanCorpusAdapter` interface.
5. Local fixture corpus adapter.
6. `get_predicate_examples` tool.
7. Repair context builder.
8. Patch generator interface and null adapter.
9. Suppression proposal path.
10. Sandbox workspace manager.
11. Analyser rerun integration.
12. SARIF delta verifier.
13. Build/test rerun integration.
14. Remaining-risk note generator.
15. `SASTRepairReport` assembler.
16. `run_sast_repair` task-capable tool.
17. Rule-evolution stub.
18. `sast-repair` skill template.

Reasoning:

- Binding and classification must exist before context can be assembled.
- Predicate examples are the most valuable context signal and should be tested early.
- Null adapter allows full pipeline test before LLM integration.
- SARIF delta verifier is the primary success gate and must be solid before reporting.

---

## 23. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 12 |
|---|---|
| Phase 13 - Bug-resolve | `run_sast_repair` as the SARIF-alert repair path when bug is a SAST finding; `SASTRepairReport` in final report |
| Phase 14 - Implementation-check | `AlertBinding` and `AlertClassification` for clause-level SARIF evidence |
| Phase 15 - Blast radius | Changed-symbol records from `AlertBinding` for impact analysis |
| Phase 17 - Memory | `SASTRepairReport.verdict` and `remaining_risk_note` for trajectory outcome labelling |
| Phase 18 - Release gates | Repair success rate, false-positive suppression precision, remaining-risk note rate |
| Phase 19 - Distribution | `run_sast_repair`, `get_predicate_examples` tools; `sast-repair` template |

---

## 24. Exit Criteria Mapping

Source Phase 12 exit criterion:

- `run_sast_repair(alert_id)` can propose a patch for a known alert fixture.

Concrete acceptance:

- Null-mode run produces `SASTRepairReport` with `SASTPatch` reference.
- Report includes alert binding, classification, examples, SARIF delta, and build/test result.
- `HarnessConditionSheet` attached.

Source Phase 12 exit criterion:

- The original alert must disappear before the alert can be considered fixed.

Concrete acceptance:

- `SARIFDeltaVerificationResult.original_alert_gone: true` required for `alert_fixed` verdict.
- `original_alert_remains: true` → verdict `repair_failed`; fixture test passes.

Source Phase 12 exit criterion:

- New higher-severity alerts block success.

Concrete acceptance:

- `new_critical_or_error_alerts: non-empty` → verdict `repair_blocked`; fixture test passes.

Source Phase 12 exit criterion:

- Confirmed false positives can produce a reviewed suppression or offline rule-evolution candidate, but not an unreviewed analyser-rule mutation.

Concrete acceptance:

- False-positive fixture produces `SuppressionProposal` with `reviewer_required: true`.
- `evolve_static_rules` stub returns `not_implemented`.
- No fixture test can trigger an automatic rule mutation.

---

## 25. Definition Of Done

Phase 12 is done when:

- Alert binding maps SARIF alerts to graph nodes with `confidence` metadata.
- Alert classification produces `likely_true_positive`, `likely_false_positive`, or `unknown`.
- Predicate-example retrieval returns examples by predicate-negation method for fixture alerts.
- `get_predicate_examples` tool is implemented and tested.
- Repair context builder assembles graph slice, examples, and explanation within budget.
- `PatchGeneratorInterface` is abstract with null adapter for testing.
- Suppression proposal path generates proposals with `reviewer_required: true`.
- Sandbox applies patch without touching registered repo root.
- Analyser rerun produces after-repair SARIF.
- SARIF delta verifier produces correct success/block verdicts for all fixture cases.
- Build/test rerun flags newly failing tests as block conditions.
- Remaining-risk notes generated for vulnerability-class alerts without PoC+.
- `run_sast_repair` task-capable tool completes null-mode run with full `SASTRepairReport`.
- `evolve_static_rules` stub returns `not_implemented` with gate documentation.
- `sast-repair` skill template renders with stable snapshot.
- All block conditions in SARIF delta and test rerun are deterministic and unconditional.

---

## 26. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Alert binding fails silently on stale graph | Context missing key symbols; repair misses root cause | Require `confidence` field on all bindings; stale snapshot triggers diagnostic; never silently drop bindings |
| Predicate examples from target repo contaminate context | Model reproduces memorised code | Corpus adapter must exclude target repo by repo ID; test with fixture that overlaps target repo |
| Analyser rerun applies to full repo instead of changed files | Slow repair loops; false new alerts from unrelated code | Scope rerun to changed files where analyser supports it; log diagnostic when forced to full-repo run |
| `original_alert_remains: true` reported as `alert_fixed` | False repair claims | `SARIFDeltaVerificationResult.success` requires both `original_alert_gone: true` AND `new_critical_or_error_alerts: []`; test is required |
| False-positive suppression bypasses review | FP suppressions accumulate without human review | All suppression proposals have `reviewer_required: true`; rule mutations require offline gate |
| Build/test rerun finds no tests covering changed files | Test coverage gap not detected | Log test-coverage-absent diagnostic; fall back to full suite; record in `BuildTestResult` |
| `run_sast_repair` races against ongoing `graph_update` | Alert binding uses stale graph mid-repair | Record snapshot ID at binding time; compare to graph at rerun time; emit stale-snapshot warning |
| Sandbox not cleaned up | Workspace fills with stale patches | Sandbox cleanup runs in finally-block; cleanup failure is a non-fatal diagnostic; workspace monitor in Phase 4A |

---

## 27. Phase 12 Completion Report Template

When Phase 12 implementation is complete, report:

```text
Phase 12 completion report

Implemented:
- Alert binding (confidence levels):
- Alert classification (TP/FP/unknown evidence):
- Predicate metadata extraction:
- Predicate example retrieval:
- Clean corpus adapter (local fixture):
- get_predicate_examples tool:
- Repair context builder:
- PatchGeneratorInterface and null adapter:
- Suppression proposal path:
- Sandbox workspace manager:
- Analyser rerun integration:
- SARIF delta verifier:
- Build/test rerun integration:
- Remaining-risk note generator:
- run_sast_repair task-capable tool:
- evolve_static_rules stub:
- sast-repair skill template:

Verification:
- Alert binding tests:
- Alert classification tests:
- Predicate example tests:
- Repair loop tests (null mode):
- SARIF delta tests:
- Build/test rerun tests:
- Suppression proposal tests:
- Full tool tests:
- Template snapshot tests:

Exit criteria:
- run_sast_repair proposes patch for fixture alert:
- Original alert must disappear for fixed verdict:
- New higher-severity alerts block success:
- False positives produce reviewed suppression only:

Known limitations:
-

Follow-up for Phase 13:
-
```

---

## 28. Minimal First Slice Within Phase 12

If Phase 12 needs to be split further, implement this first:

1. `AlertBinding` model and algorithm.
2. `AlertClassification` model and true-positive/false-positive rules.
3. `PredicateMetadata` model and extraction.
4. `PredicateExampleRecord` model and `LocalFixtureCorpusAdapter`.
5. `get_predicate_examples` tool.
6. `RepairContext` model and builder.
7. `PatchGeneratorInterface` abstract and null adapter.
8. `SASTPatch` model.
9. `SARIFDeltaVerificationResult` model and verifier.
10. `SASTRepairReport` model (partial).
11. `run_sast_repair` null-mode task tool.

This minimal slice establishes the PredicateFix retrieval pattern, the SARIF delta verification gate, and the null-mode pipeline that Phase 13 can call for SARIF-class bugs in the bug-resolve workflow.
