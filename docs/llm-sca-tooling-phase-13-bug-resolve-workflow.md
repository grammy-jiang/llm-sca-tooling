# LLM-SCA Tooling Phase 13 Implementation Plan: Bug-Resolve Workflow

> Date: 2026-05-09
> Repository name: `evidence-sca`
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 13 - Bug-Resolve Workflow
> Primary objective: build the first end-to-end issue-resolution workflow — a ten-stage state machine that runs investigate → repair → DryRUN prediction → deterministic gates → patch-risk review → blast-radius → scope/permission audit → operational review pre-check → trajectory recording, producing a typed final report with run record and Harness Condition Sheet.

---

## 1. Phase Summary

Phase 13 is the first end-to-end workflow phase of `evidence-sca`. Phases 1-12 built all the evidence components: graph index, SARIF layer, fault localisation, evaluation harness, patch review gates, and SAST repair. Phase 13 wires them into a single coherent workflow that a developer can invoke with an issue description.

The central rule for this phase is:

```text
The repair workflow never presents a patch as resolved when gates disagree.
A missing trace, missing permission profile, or missing verification artefact
is an incomplete run — not a successful one.
Process-noncompliant, trace-incomplete, or budget-exhausted runs cannot
recommend merge.
Generated reproduction tests cannot count as hard evidence until they
execute, fail on the pre-fix version for the expected reason, and pass (or
explainably change) after the candidate patch.
DryRUN/actual mismatches are reported and must be resolved or accepted as
explicit residual risk.
```

Phase 13 should implement:

- Workflow state machine with ten stages.
- Repair context builder.
- Unified diff generation and validation interface.
- Pre/postcondition draft generation interface.
- Issue-anchored reproduction test support.
- Execution-free certificate schema.
- Test/build/SARIF/interface gate runner.
- Patch selection policy.
- Final report schema and assembler.
- Session trace and evidence-manifest writer.
- Monitor hooks for loop detection and budget hard-stop.
- `run_issue_resolution` task-capable tool.
- Public `bug-resolve` prompt (graduates from Phase 4 stub to full implementation).
- Private `investigate`, `repair`, `blast-radius`, and `risk-classify` skill templates.

### Architecture Coverage

Phase 13 covers:

- F5 bug-resolve.
- F11 run-record, policy, budget, and monitor integration for end-to-end workflow.
- Public `bug-resolve` prompt (fully implemented).
- Private `investigate`, `repair`, `blast-radius`, and `risk-classify` templates.
- `run_issue_resolution` tool.

Tools in this phase:

- `run_issue_resolution`

Prompt graduated in this phase:

- `bug-resolve` (from stub to full implementation)

Private skill templates in this phase:

- `investigate`
- `repair`
- `blast-radius`
- `risk-classify` (refined from Phase 11 stub)

### Inherited Paper Anchors

Use these anchors in Phase 13 issues, ADRs, and bug-resolve reports:

- `agentless`
- `fl-context-2026`
- `specrover`
- `agentic-code-reasoning`
- `agent-coevo`
- `issue2test`
- `assertflip`
- `trace-prompt`
- `daira`
- `pvbench`

## Technology Stack

This phase uses the following libraries from `llm-sca-tooling-tech-stack.md`:

| Library/Tool | PyPI package | Version | Role in this phase |
|---|---|---|---|
| Python | — | 3.12+ | Runtime |
| uv | — | latest | Environment and dependency management |
| Pydantic v2 | `pydantic` | >=2.0 | `WorkflowState`, `WorkflowConfig`, `DryRUNPrediction`, `ExecutionFreeCertificate`, `GateRunnerResult` schemas; `extra="forbid"` on all models |
| orjson | `orjson` | >=3.10 | Trajectory serialisation, patch payloads, gate results, all JSON I/O |
| NetworkX | `networkx` | >=3.3 | Blast-radius graph traversal during the repair stage |
| FastMCP + FastAPI | `fastmcp`, `fastapi` | >=2.0, >=0.115 | `run_issue_resolution` MCP tool handler |
| httpx | `httpx` | >=0.27 | `PolicyAwareHTTPClient` wrapping for HC5 |
| pytest + pytest-asyncio | `pytest`, `pytest-asyncio` | >=8.0, >=0.23 | Bug-resolve workflow tests; `asyncio_mode="auto"` |

- All subprocess calls (test/build/SARIF gate runners) use `asyncio.create_subprocess_exec`; `subprocess.run` is forbidden.
- All tool handlers and state-machine stage functions are `async def`.
- Rich is restricted to the CLI layer; all other modules use `logging`.
- Pydantic models use `model_json_schema()` for schema export; no hand-written JSON schemas.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 13 depends on:

- Phase 1 schemas:
  - `RunRecord` and `RunEvent` models
  - `Patch`, `RiskFinding`, and `Verdict` models
  - `HarnessConditionSheet` model
  - incident and promotion candidate models
- Phase 2 stores:
  - operational store for run records
  - artefact registry
  - graph store
- Phase 4 infrastructure:
  - task manager and task persistence
  - telemetry hooks and run-event linkage
  - public `bug-resolve` prompt slot (being upgraded from stub)
- Phase 5 language backends:
  - cross-language call graph for blast-radius
- Phase 6 SARIF layer:
  - SARIF run store and delta utility
  - `run_static_analysis` for post-patch SARIF check
- Phase 7 interface plugins:
  - interface traversal for blast-radius
- Phase 8 repo-QA:
  - `answer_repo_question` and `classify_repo_question` for investigation step
- Phase 9 fault localisation:
  - `get_relevant_files` (full pipeline or null mode)
  - `LocalisationResult` with `ranked_candidates`
  - `InvestigateInput` / `InvestigateOutput` handoff models
- Phase 10 evaluation harness:
  - `HarnessConditionSheet` model
  - `EvalRun` reference in final report
  - T1 smoke instances that must survive workflow addition
- Phase 11 patch review:
  - `run_patch_review` as the final safety gate
  - `classify_patch_risk` for risk classification
  - `DryRUNPrediction` contract
  - `PatchReviewReport` in final report
- Phase 12 SAST repair:
  - `run_sast_repair` for SARIF-class issues
  - `SASTRepairReport` reference when relevant

### Phase Outputs

Phase 13 should produce:

- `WorkflowConfig` model.
- `WorkflowState` and state-machine controller.
- `RepairContextRecord` model.
- `CandidatePatch` model.
- `PrePostConditionDraft` model.
- `ReproductionTestRecord` model.
- `ExecutionFreeCertificate` model.
- `GateRunnerResult` model.
- `PatchSelectionRecord` model.
- `BlastRadiusStub` model (partial implementation; Phase 15 hardens it).
- `MonitorEvent` model for loop/budget/snapshot detection.
- `BugResolveReport` model (final report).
- `SessionTraceManifest` model.
- `run_issue_resolution` task-capable tool handler.
- Fully implemented public `bug-resolve` prompt.
- Private `investigate`, `repair`, `blast-radius`, and `risk-classify` skill templates.
- Bug-resolve workflow tests.

### Non-Goals

Do not implement these in Phase 13:

- Implementation-check workflow (Phase 14).
- Full hardened blast-radius service (Phase 15 — Phase 13 uses a stub).
- Dynamic trace capture (Phase 16).
- Trajectory memory store (Phase 17 — Phase 13 records trajectory shape but does not persist).
- Full cross-repo blast-radius traversal.
- LLM-as-judge as a gate substitute.
- Patch apply to the registered repository root (apply only in sandbox or explicitly requested).

---

## 3. Recommended File Layout

Assuming package name `evidence_sca`:

```text
src/evidence_sca/
  workflows/
    __init__.py
    bug_resolve/
      __init__.py
      config.py
      state_machine.py
      models.py
      investigate.py
      repair_context.py
      candidate_patch.py
      preconditions.py
      reproduction_test.py
      certificate.py
      gate_runner.py
      patch_selection.py
      blast_radius_stub.py
      monitor_hooks.py
      report.py
      trace_manifest.py

  mcp_server/
    tools/
      issue_resolution.py
    prompts/
      bug_resolve.md

  skills/
    investigate.md
    repair.md
    blast_radius.md
    risk_classify.md

tests/
  workflows/
    bug_resolve/
      fixtures/
        issues/
          simple_nullderef.json
          multi_file_logic_error.json
          sarif_security_alert.json
          ambiguous_issue.json
          budget_exhausted_issue.json
        gold/
          simple_nullderef_patch.diff
          multi_file_logic_error_patch.diff
      test_state_machine.py
      test_investigate.py
      test_repair_context.py
      test_candidate_patch.py
      test_preconditions.py
      test_reproduction_test.py
      test_certificate.py
      test_gate_runner.py
      test_patch_selection.py
      test_blast_radius_stub.py
      test_monitor_hooks.py
      test_report.py
      test_trace_manifest.py
      test_run_issue_resolution.py
      test_bug_resolve_prompt.py
      test_investigate_template.py
      test_repair_template.py
```

---

## 4. Workflow Configuration

### 4.1 `WorkflowConfig` Model

Required fields:

```text
WorkflowConfig
  max_candidates
  max_repair_loops
  max_gate_retries
  context_budget
  token_budget
  wall_clock_budget_seconds
  fl_budget
  require_reproduction_test
  require_blast_radius
  require_patch_review
  require_sarif_gate
  require_interface_gate
  null_mode
  permission_profile
  policy_id
  sandbox_only
```

### 4.2 Default Configuration

Defaults:

- `max_candidates: 3`
- `max_repair_loops: 5`
- `require_reproduction_test: true`
- `require_blast_radius: true`
- `require_patch_review: true`
- `require_sarif_gate: true`
- `require_interface_gate: true`
- `sandbox_only: true` (never apply patch to registered repo root without explicit opt-in)
- `null_mode: false`

---

## 5. Workflow State Machine

### 5.1 Stages

The workflow state machine has ten stages:

1. **load**: Load `AGENTS.md`, manifest, `HarnessConditionSheet`, and create run record.
2. **investigate**: Run Phase 9 fault localisation; classify issue via Phase 8 repo-QA.
3. **repair**: Generate candidate patch(es) using `repair` template.
4. **dryrun**: Generate DryRUN prediction for each candidate.
5. **gates**: Run deterministic gates: SARIF delta, build/test, interface-contract compatibility.
6. **patch_risk**: Run Phase 11 `classify_patch_risk` on passing candidates.
7. **blast_radius**: Run blast-radius stub to identify affected callers/interfaces/repos.
8. **scope_audit**: Run Phase 11 scope/permission audit.
9. **operational_review**: Pre-check operational compliance from run record.
10. **trajectory**: Record trajectory shape (not persisted to memory until Phase 17).

### 5.2 `WorkflowState` Model

Required fields:

```text
WorkflowState
  run_id
  stage
  stage_history
  investigate_result
  repair_candidates
  dryrun_predictions
  gate_results
  patch_risk_results
  blast_radius_result
  scope_audit_result
  operational_verdict
  selected_patch
  final_report_ref
  status
  error
  loop_count
  monitor_events
```

`status` values:

- `running`
- `completed_success`
- `completed_no_fix`
- `completed_uncertain`
- `failed`
- `cancelled`
- `budget_exhausted`

### 5.3 State Transition Rules

Rules:

- Each stage can transition to `failed` or `budget_exhausted` without entering later stages.
- If `investigate` produces an empty suspect list, the workflow transitions to `completed_no_fix` with `unknown` verdict.
- If all repair candidates fail gates, the workflow transitions to `completed_no_fix`.
- If `scope_audit` finds out-of-scope writes, all passing candidates are downgraded.
- The workflow never reuses a failed candidate in a second repair loop.
- The workflow checks for doom-loop candidates (section 11.1) at each repair-loop increment.

---

## 6. Investigate Stage

### 6.1 Purpose

The investigate stage combines Phase 9 fault localisation with Phase 8 repo-QA to produce a ranked suspect list and additional behavioural context.

### 6.2 Integration with Phase 9

The investigate stage calls `get_relevant_files` from Phase 9 with the issue text normalised by Phase 9's `IssueTextNormalizer`. It receives a `LocalisationResult` with `ranked_candidates`, `budget_used`, `agreement_score`, and `provenance`.

### 6.3 Integration with Phase 8

After fault localisation, the investigate stage queries Phase 8's `answer_repo_question` for:

- Behavioural context questions about the suspect functions.
- File-location confirmation questions for each top-3 suspect.

Answers with `confidence < 0.5` are treated as `unknown` and not propagated as hard evidence to the repair stage.

### 6.4 `InvestigateResult` Model

Required fields:

```text
InvestigateResult
  run_id
  issue_text_hash
  localisation_result_ref
  ranked_candidates
  top3_file_suspects
  repo_qa_answers
  behavioural_context
  agreement_score
  budget_used
  snapshot_id
  stale_snapshot_flag
  confidence
  diagnostics
```

### 6.5 Rules

Rules:

- If graph snapshot is stale relative to the issue timestamp, set `stale_snapshot_flag: true` and include in the final report uncertainty.
- An empty `ranked_candidates` from Phase 9 is not an error; it produces `completed_no_fix`.
- Repo-QA answers with `QuestionClass.BEHAVIOUR_TRACE` that fail the Phase 8 ship gate (≥70% accuracy required) are tagged as supporting evidence, not hard evidence.

---

## 7. Repair Context Builder

### 7.1 Purpose

The repair context assembles the bounded evidence window that the `repair` template uses to generate a candidate patch. It must respect the context budget.

### 7.2 `RepairContextRecord` Model

Required fields:

```text
RepairContextRecord
  run_id
  candidate_index
  file_suspects
  graph_slices_ref
  summaries_ref
  blame_chain_refs
  sarif_alerts_in_scope
  interface_contracts_ref
  snapshot_id
  language
  context_tokens_estimate
  budget_remaining
  provenance
```

### 7.3 Budget Rules

Following `fl-context-2026` (6-10 file sweet spot):

- Default starting budget: top-6 suspects from `InvestigateResult`.
- If top-6 produces insufficient context (few edges, few callers), expand to top-10.
- Beyond top-10 requires an explicit uncertainty note in the report.
- If budget is exhausted before graph slices can be assembled, log a budget event and transition to `budget_exhausted`.

---

## 8. Candidate Patch Generation

### 8.1 `CandidatePatch` Model

Required fields:

```text
CandidatePatch
  run_id
  candidate_index
  diff_text
  diff_format
  changed_files
  changed_symbol_ids
  generation_method
  generator_model
  reasoning_chain
  certificate_ref
  precondition_draft_ref
  postcondition_draft_ref
  confidence
  provenance
```

### 8.2 Patch Generation Interface

The patch generation interface is the LLM boundary within the `repair` template. It receives a `RepairContextRecord` and returns a `CandidatePatch`. The null adapter returns a deterministic minimal diff for testing.

Rules:

- The generator must use the graph slice and summaries as primary context.
- Source files are included only when the evidence model says exact code is needed for the patch.
- Generated patches must be valid unified diffs before proceeding to the gate stage.

### 8.3 Pre/Postcondition Draft Generation

The pre/postcondition draft generator creates explicit artefacts for changed functions where the workflow can infer them.

`PrePostConditionDraft` model:

```text
PrePostConditionDraft
  run_id
  candidate_index
  function_path
  preconditions
  postconditions
  generation_method
  confidence
```

Rules:

- Pre/postconditions are generated as supporting evidence, never as hard predicates unless they also compile or pass a linter.
- `compile_status: unknown` when the pre/postcondition cannot be automatically verified.

---

## 9. Reproduction Test Support

### 9.1 Purpose

Following the `issue2test` and `assertflip` patterns, the workflow should attempt to generate a failing reproduction test when none is provided. The test must fail on the pre-fix version for the expected reason before it can count as hard evidence.

### 9.2 `ReproductionTestRecord` Model

Required fields:

```text
ReproductionTestRecord
  run_id
  candidate_index
  test_code
  test_file
  generation_method
  pre_fix_result
  post_fix_result
  fails_for_expected_reason
  flaky_flag
  flaky_entropy_score
  generated_test_is_hard_evidence
  diagnostics
```

`pre_fix_result` and `post_fix_result` values:

- `pass`
- `fail`
- `error`
- `not_executed`
- `flaky`

### 9.3 Rules for Hard Evidence

Rules:

- `generated_test_is_hard_evidence: true` requires:
  1. `pre_fix_result: fail`.
  2. `post_fix_result: pass` or `post_fix_result: fail` with an explicit explanation of why the changed behaviour is expected.
  3. `fails_for_expected_reason: true` (the failure reason matches the issue description).
  4. `flaky_flag: false`.
- A test that passes on both pre-fix and post-fix versions is not evidence.
- Generated tests must be kept separate from production changes until they satisfy the hard-evidence criteria.

### 9.4 `assertflip` Note

The `assertflip` pattern generates a test that asserts the buggy behaviour, then inverts the assertion for the fix. The workflow should attempt this only when the issue description contains a clear observable failure (exception, wrong return value, assertion error) rather than a structural/maintainability issue.

---

## 10. Execution-Free Certificate

### 10.1 Purpose

Following the `specrover` and `agentic-code-reasoning` patterns, the workflow generates an execution-free certificate for each candidate patch. The certificate is a structured argument for why the patch addresses the root cause, expressed without running the code.

### 10.2 `ExecutionFreeCertificate` Model

Required fields:

```text
ExecutionFreeCertificate
  run_id
  candidate_index
  definitions
  premises
  path_claims
  counterexample_search
  conclusion
  evidence_refs
  confidence
  unsupported_claims
```

`conclusion` values:

- `supported`: all premises are supported by graph/SARIF/test evidence; no counterexample found.
- `partially_supported`: some premises unverified; conclusion is conditional.
- `unsupported`: counterexample found or premises contradict evidence.
- `unknown`: insufficient evidence to evaluate.

### 10.3 Rules

Rules:

- The certificate is generated from graph evidence and predicate/static facts, not from LLM introspection alone.
- `unsupported_claims` must be listed explicitly.
- A `conclusion: unsupported` certificate is a soft block signal for the gate runner.

---

## 11. Gate Runner

### 11.1 Purpose

The gate runner executes the deterministic verification gates for each candidate patch and aggregates the results.

### 11.2 `GateRunnerResult` Model

Required fields:

```text
GateRunnerResult
  run_id
  candidate_index
  sarif_gate_pass
  sarif_delta_ref
  build_gate_pass
  test_gate_pass
  required_test_result
  reproduction_test_result
  poc_plus_result
  interface_gate_pass
  interface_compat_ref
  certificate_conclusion
  overall_gate_pass
  block_reasons
```

### 11.3 Gate Definitions

Gates and pass conditions:

- **SARIF gate**: no new critical or security-class alerts after applying patch in sandbox and re-running analyser. Uses Phase 12's delta utility.
- **Build gate**: patched code builds in the sandbox environment.
- **Test gate**: no required tests fail after the patch. Flaky tests are excluded.
- **Required test gate**: the reproduction test (if generated and hard-evidence) fails on pre-fix and passes on post-fix.
- **PoC+ gate**: relevant only for vulnerability-class issues. PoC+ test passes after the patch.
- **Interface gate**: no breaking interface changes detected by Phase 11's compatibility checker.

### 11.4 Override Rules

Rules:

- Any block reason overrides `overall_gate_pass: true` unconditionally.
- Block reasons: new critical SARIF alert, failing required test, PoC+ failure, interface breaking change, `certificate_conclusion: unsupported` (soft block — logged but does not unconditionally block).
- A patch that passes all hard gates but has `certificate_conclusion: unsupported` is flagged `correct-but-overfit_risk` in the patch risk step.

### 11.5 Retry Policy

Rules:

- Gate runner retries are limited to `WorkflowConfig.max_gate_retries`.
- Retry on test flakiness only; never retry on SARIF, interface, or certificate block.
- After `max_gate_retries` exhausted: transition to `failed` with explicit retry-exhausted event.

---

## 12. Patch Selection Policy

### 12.1 Purpose

When multiple candidates pass all hard gates, the selection policy picks the best one.

### 12.2 `PatchSelectionRecord` Model

Required fields:

```text
PatchSelectionRecord
  run_id
  candidates_evaluated
  selected_candidate_index
  selection_rationale
  selection_criteria
  rejected_candidates
  rejection_reasons
```

### 12.3 Selection Criteria

Priority order:

1. Higher `LocalisationResult.agreement_score` (candidates whose evidence is more strongly supported are preferred).
2. Fewer changed graph nodes (smaller blast radius).
3. Lower patch-risk probability from Phase 11 `classify_patch_risk`.
4. No new SARIF alerts (even non-critical ones).
5. Better generated-test / PoC+ survival.
6. Do not select by pass/fail count alone.

Rules:

- If all candidates have equal agreement scores and comparable risk, select the one with fewest changed graph nodes.
- If no candidate passes all gates, `selected_candidate_index: null` and workflow transitions to `completed_no_fix`.

---

## 13. Blast-Radius Stub

### 13.1 Purpose

Phase 13 includes a partial blast-radius implementation sufficient for the bug-resolve report. Phase 15 hardens this into a standalone cross-language, cross-repo service.

### 13.2 `BlastRadiusStub` Model

Required fields:

```text
BlastRadiusStub
  run_id
  candidate_index
  changed_symbol_ids
  direct_callers
  downstream_tests
  interface_boundaries
  cross_language_candidates
  ambiguous_links
  confirmed_links
  local_impact_count
  is_partial
  diagnostics
```

### 13.3 Phase 13 Scope

In Phase 13, the blast-radius stub:

- Traverses two hops of `calls` edges from changed symbols.
- Reports `tests` edges.
- Reports interface boundaries from Phase 7.
- Marks all cross-repo and cross-language links as `is_partial: true`.
- Does not traverse cross-repo graphs (Phase 15 adds this).

---

## 14. Monitor Hooks

### 14.1 Purpose

Monitor hooks detect pathological workflow states and enforce hard budget limits before they become silent failures.

### 14.2 `MonitorEvent` Model

Required fields:

```text
MonitorEvent
  run_id
  monitor_type
  stage
  loop_count
  detail
  severity
  action_taken
```

`monitor_type` values:

- `doom_loop_candidate`: the workflow has entered the same stage more than `max_repair_loops` times.
- `repeated_failing_gate`: the same gate has failed on successive candidates without any change in evidence.
- `context_budget_hard_stop`: context tokens have reached the hard limit.
- `token_budget_hard_stop`: total tokens have reached the hard limit.
- `wall_clock_budget_hard_stop`: wall clock time has reached the hard limit.
- `stale_snapshot_detected_before_final_report`: the graph snapshot has advanced since the investigation started.

### 14.3 Monitor Actions

Action per type:

- `doom_loop_candidate`: increment counter; at `max_repair_loops`, transition to `failed` with this event as the reason.
- `repeated_failing_gate`: log and continue; if the same gate fails five consecutive times on different candidates, transition to `completed_no_fix`.
- Budget hard-stops: emit event, flush run record, transition to `budget_exhausted`.
- `stale_snapshot_detected_before_final_report`: include stale-snapshot flag in final report uncertainty.

---

## 15. Scope and Permission Audit (Workflow Integration)

The workflow calls Phase 11's scope audit model to verify that the patch-producing run (if running in a tracked execution context) has not written to paths outside the allowlist, called network-restricted tools, or skipped required approvals.

Rules:

- If no run record is attached (standalone `run_issue_resolution` call), log diagnostic and treat scope audit as `unknown`.
- Out-of-scope writes produce a `block` scope verdict and prevent `merge-supporting` recommendation.
- Trace-incomplete verdict prevents `merge-supporting` recommendation.

---

## 16. Operational Review Pre-Check

The operational review pre-check queries the Phase 4A operational store for:

- Outstanding incidents related to the issue or the affected symbols.
- Prior failed repair attempts for the same issue (from run records, not memory — memory is Phase 17).
- Budget overruns from previous runs on the same repo.

Results are included in the final report's `operational_verdict` field. Outstanding incidents do not block the repair verdict but must appear in the final report.

---

## 17. `BugResolveReport` Model

### 17.1 Required Fields

```text
BugResolveReport
  report_id
  run_id
  harness_condition_id
  issue_text_hash
  investigate_result_ref
  selected_patch_ref
  candidate_patches_ref
  precondition_draft_ref
  postcondition_draft_ref
  reproduction_tests_ref
  certificate_ref
  gate_results_ref
  patch_risk_result_ref
  blast_radius_result_ref
  scope_audit_result_ref
  patch_review_report_ref
  dryrun_prediction_ref
  dryrun_mismatches_ref
  operational_verdict
  incident_links
  final_verdict
  recommendation
  uncertainty
  session_trace_manifest_ref
  created_ts
```

`final_verdict` values:

- `resolved`: all hard gates pass, SARIF gate pass, tests pass, certificate supported.
- `resolved_with_risk`: all hard gates pass but remaining-risk notes non-empty or certificate partially supported.
- `no_fix_found`: no candidate passed all hard gates.
- `uncertain`: inconclusive evidence or stale snapshot at final report time.
- `process_noncompliant`: run failed process compliance, recommendation blocked.
- `budget_exhausted`: workflow hit a hard budget limit.

`recommendation` values:

- `merge-supporting`: `final_verdict: resolved` AND `process_compliant`.
- `review-required`: any remaining-risk note, or `resolved_with_risk`.
- `block`: any deterministic block condition or process violation.
- `unknown`: insufficient evidence.

---

## 18. `run_issue_resolution` Tool

### 18.1 Purpose

Execute the ten-stage bug-resolve workflow for an issue text and return a task handle for polling.

### 18.2 Input

```text
issue_text
repos?
budget?
config?
null_mode?
task?
```

### 18.3 Output

- `TaskCreateResult` for the workflow task.
- On completion: `BugResolveReport` reference with run record and `HarnessConditionSheet`.

### 18.4 Workflow

1. Parse and normalise `issue_text` (Phase 9 normaliser).
2. Create `RunRecord` and task.
3. Load manifest and `HarnessConditionSheet` metadata.
4. Stage: **load** — record workflow config, permission profile, context budget.
5. Stage: **investigate** — call `get_relevant_files`; call `answer_repo_question` for behavioural context.
6. If no suspects: transition to `completed_no_fix`.
7. Loop for each repair attempt:
   a. Stage: **repair** — build `RepairContextRecord`; generate `CandidatePatch`.
   b. Stage: **dryrun** — generate `DryRUNPrediction`; generate reproduction test.
   c. Stage: **gates** — run SARIF gate, build gate, test gate, interface gate.
   d. Check monitor hooks (doom-loop, repeated failing gate, budget).
   e. If gates pass: proceed to risk stage.
   f. If gates fail: record failure, increment loop count, attempt next candidate.
8. Stage: **patch_risk** — call `classify_patch_risk`; compute `PatchSelectionRecord`.
9. Stage: **blast_radius** — run blast-radius stub.
10. Stage: **scope_audit** — run Phase 11 scope audit.
11. Stage: **operational_review** — pre-check operational compliance.
12. Stage: **trajectory** — record trajectory shape for Phase 17 consumption.
13. Assemble `BugResolveReport`.
14. Attach `HarnessConditionSheet`.
15. Run `run_patch_review` if `require_patch_review: true`.
16. Finalise `final_verdict` and `recommendation`.
17. Store report artefact.
18. Emit `notifications/resources/updated` for run resource.
19. Return report.

### 18.5 Permissions

- Required mode: read/search for investigation and gate checking; execute for sandbox-based patch application, analyser rerun, and test execution.
- Path scope: registered repos and sandbox workspace.
- Network: none.
- Side effect: writes sandbox workspace, artefact store, and operational records.
- Approval: sandbox execution and test execution require execute mode.

### 18.6 Tests

Required tests:

- Full workflow null-mode run for `simple_nullderef` fixture: produces `BugResolveReport`.
- Null-mode run for `ambiguous_issue` fixture: produces `completed_no_fix` or `uncertain` verdict.
- Gate failure on new-critical SARIF fixture: `recommendation: block`.
- Budget-exhausted monitor hook fires correctly.
- Doom-loop monitor hook fires at `max_repair_loops`.
- `HarnessConditionSheet` attached to every report.
- Trace-incomplete run cannot produce `merge-supporting` recommendation.

---

## 19. Public `bug-resolve` Prompt

### 19.1 Graduation from Stub to Full Implementation

In Phase 4 the `bug-resolve` prompt was a stub that listed future tools and limitations. Phase 13 replaces it with a fully implemented prompt that:

- Accepts `issue_text`, `repos?`, and `budget?` arguments.
- Describes the ten-stage workflow clearly.
- Lists all resources and tools the MCP client should expect to be called.
- States: what `run_issue_resolution` will do, what gates will be checked, what evidence will be in the report.
- States Sampling availability and fallback behaviour.
- States the evidence discipline: `unknown` is preserved when evidence is stale, missing, or ambiguous.

### 19.2 Prompt Arguments

```text
issue_text
repos?
budget?
```

### 19.3 Prompt Behaviour Rules

Rules:

- The prompt does not itself execute the workflow; it returns structured instructions and tool/resource references.
- The prompt mentions `run_issue_resolution` as the workflow launcher.
- The prompt states that a `merge-supporting` recommendation requires process-compliant run AND all hard gates passing.
- The prompt includes a note about DryRUN prediction and mismatch reporting.
- The prompt snapshot must be stable.

---

## 20. Private Skill Templates

### 20.1 `investigate` Template

Entry: `investigate(issue_text, repos?, budget?)`.

The template instructs the agent to:

1. Normalise the issue text.
2. Call `get_relevant_files(issue_text)`.
3. For each top-3 suspect: call `get_graph_slice` and `get_interface_contract`.
4. Call `answer_repo_question` for behavioural context.
5. Assemble `InvestigateResult`.
6. State ranked suspects with agreement scores.
7. Flag stale snapshot if present.
8. Flag if repo-QA answers are below the ship-gate confidence threshold.

### 20.2 `repair` Template

Entry: `repair(investigate_result, candidate_index?, issue_context?)`.

The template instructs the agent to:

1. Load the graph slice for the top fault locations.
2. Check for cross-language interface contracts that the symbol participates in (from Phase 7).
3. If the issue maps to a SARIF alert: call `run_sast_repair`.
4. Otherwise: generate a patch in unified diff format using the graph slice and summaries.
5. Generate pre/postconditions for changed functions.
6. Generate reproduction test draft (assertflip when applicable).
7. Generate execution-free certificate.
8. Return `CandidatePatch` with all artefact references.

Rules:

- Template must load bounded source spans only when the evidence model indicates exact code is needed.
- Template must never generate patches that write to files outside the changed-symbols scope.
- Template snapshot must be stable.

### 20.3 `blast-radius` Template

Entry: `blast-radius(change_set, repos?)`.

The template instructs the agent to:

1. Load graph slices for all changed symbols.
2. Trace outward through `calls` and interface edges.
3. Report direct callers, downstream behaviours, tests, interfaces, and services.
4. Report generated-file impact and source contract.
5. Separate confirmed links from candidate links.
6. Return `BlastRadiusStub` or, in Phase 15, a full `BlastRadiusReport`.

### 20.4 `risk-classify` Template

Refined from Phase 11 with additional context from Phase 13:

- Includes `InvestigateResult.agreement_score` as an additional context field.
- Flags `correct-but-overfit_risk` when certificate conclusion is `unsupported` despite passing tests.

### 20.5 Template Tests

Required tests:

- All four templates render with required arguments.
- All snapshots stable.
- `investigate` template includes stale-snapshot flag logic.
- `repair` template includes SARIF repair path.
- `blast-radius` template separates confirmed and candidate links.

---

## 21. Session Trace and Evidence-Manifest Writer

### 21.1 `SessionTraceManifest` Model

Required fields:

```text
SessionTraceManifest
  run_id
  workflow
  issue_text_hash
  repos
  start_ts
  end_ts
  stage_sequence
  artefact_refs
  tool_calls
  gate_events
  monitor_events
  budget_events
  approval_events
  redaction_policy
  harness_condition_id
```

### 21.2 Rules

Rules:

- The trace manifest must be writable from any stage without blocking the workflow.
- Artefact references must be hash-verified before inclusion.
- Redaction policy must be applied before writing prompt text or source spans.
- The trace manifest is the operational substrate for Phase 18 release-gate replay.

---

## 22. Test Plan

### 22.1 Model Tests

Required:

- All Phase 13 models round-trip through JSON.
- `final_verdict` enum exhaustive.
- `recommendation` enum exhaustive.
- Missing required fields fail validation.

### 22.2 Stage Tests

Required per stage:

- **investigate**: suspects produced from fixture; empty suspect list transitions to `no_fix_found`.
- **repair**: `CandidatePatch` produced; null mode returns deterministic diff.
- **dryrun**: `DryRUNPrediction` and reproduction test generated.
- **gates**: SARIF gate pass and fail; build gate; test gate; interface gate.
- **patch_risk**: `PatchRiskResult` produced; selection criteria applied.
- **blast_radius**: stub report produced with `is_partial: true`.
- **scope_audit**: out-of-scope write detected.
- **operational_review**: incident links included.
- **trajectory**: trajectory shape recorded.

### 22.3 Monitor Hook Tests

Required:

- Doom-loop monitor fires at `max_repair_loops`.
- Repeated-failing-gate monitor fires after five consecutive failures.
- Context-budget hard-stop transitions to `budget_exhausted`.
- Stale-snapshot monitor sets flag in report.

### 22.4 Full Workflow Tests

Required:

- Null-mode run for `simple_nullderef`: `resolved` verdict.
- Null-mode run for `ambiguous_issue`: `uncertain` or `no_fix_found`.
- SARIF gate failure fixture: `block` recommendation.
- Trace-incomplete run: no `merge-supporting` recommendation.
- All gates pass with full `HarnessConditionSheet`.

### 22.5 Prompt and Template Tests

Required:

- `bug-resolve` prompt renders and snapshot stable.
- All four private templates render and snapshots stable.
- `bug-resolve` prompt mentions `run_issue_resolution`.
- `repair` template includes SARIF repair path.

---

## 23. Work Packages

### P13.1 Workflow Config and State Machine

Build:

- `WorkflowConfig` model.
- `WorkflowState` model.
- State machine controller with ten stages and transition rules.

Deliverables:

- `workflows/bug_resolve/config.py`
- `workflows/bug_resolve/state_machine.py`
- State machine tests.

Acceptance:

- State machine transitions correctly for success and failure cases.

### P13.2 Investigate Stage

Build:

- `InvestigateResult` model.
- Phase 9 and Phase 8 integration.
- Stale-snapshot detection.

Deliverables:

- `workflows/bug_resolve/investigate.py`
- Investigate tests.

Acceptance:

- Suspects produced for fixture issues; empty list handled.

### P13.3 Repair Context and Candidate Patch

Build:

- `RepairContextRecord` model.
- Budget-aware context assembler.
- `CandidatePatch` model.
- Patch generator interface and null adapter.
- Pre/postcondition draft generator.

Deliverables:

- `workflows/bug_resolve/repair_context.py`
- `workflows/bug_resolve/candidate_patch.py`
- `workflows/bug_resolve/preconditions.py`
- Tests.

Acceptance:

- Context and patch produced in null mode.

### P13.4 Reproduction Test and Certificate

Build:

- `ReproductionTestRecord` model.
- Assertflip generator stub.
- Hard-evidence validation.
- `ExecutionFreeCertificate` model.
- Certificate builder.

Deliverables:

- `workflows/bug_resolve/reproduction_test.py`
- `workflows/bug_resolve/certificate.py`
- Tests.

Acceptance:

- Reproduction test requires pre-fix fail for hard evidence; certificate model populated.

### P13.5 Gate Runner

Build:

- `GateRunnerResult` model.
- SARIF gate wiring from Phase 12.
- Build and test gate runner.
- Interface gate wiring from Phase 11.
- Block-condition evaluator.
- Retry policy.

Deliverables:

- `workflows/bug_resolve/gate_runner.py`
- Gate runner tests.

Acceptance:

- Gate pass/fail correct for all fixture cases.

### P13.6 Patch Selection and Blast-Radius Stub

Build:

- `PatchSelectionRecord` model.
- Multi-criterion selection logic.
- `BlastRadiusStub` model.
- Two-hop caller traversal.

Deliverables:

- `workflows/bug_resolve/patch_selection.py`
- `workflows/bug_resolve/blast_radius_stub.py`
- Tests.

Acceptance:

- Correct candidate selected from fixture; blast-radius stub produces partial report.

### P13.7 Monitor Hooks and Scope/Operational Checks

Build:

- `MonitorEvent` model.
- Doom-loop and repeated-failing-gate monitors.
- Budget hard-stop hooks.
- Stale-snapshot detector.
- Phase 11 scope audit wiring.
- Operational review pre-check.

Deliverables:

- `workflows/bug_resolve/monitor_hooks.py`
- Tests.

Acceptance:

- Doom-loop fires at limit; budget hard-stop transitions state.

### P13.8 `BugResolveReport` and Trace Manifest

Build:

- `BugResolveReport` model.
- Report assembler.
- `SessionTraceManifest` model and writer.
- `final_verdict` and `recommendation` computation.

Deliverables:

- `workflows/bug_resolve/report.py`
- `workflows/bug_resolve/trace_manifest.py`
- Tests.

Acceptance:

- Report assembled with all required fields; trace manifest written.

### P13.9 `run_issue_resolution` Tool

Build:

- Task-capable tool handler.
- Full workflow orchestration wiring.
- `HarnessConditionSheet` assembly.
- Resource update notification.

Deliverables:

- `mcp_server/tools/issue_resolution.py`
- Full tool tests.

Acceptance:

- MCP client can launch, poll, and read bug-resolve report.

### P13.10 Prompts and Templates

Build:

- Fully implemented `bug-resolve` public prompt.
- `investigate.md` template.
- `repair.md` template.
- `blast_radius.md` template.
- `risk_classify.md` refinement.
- All snapshot tests.

Deliverables:

- `mcp_server/prompts/bug_resolve.md`
- `skills/investigate.md`
- `skills/repair.md`
- `skills/blast_radius.md`
- `skills/risk_classify.md`
- Template tests.

Acceptance:

- All templates render; all snapshots stable.

---

## 24. Suggested Implementation Order

Recommended order:

1. Workflow config and state machine.
2. `InvestigateResult` model and investigate stage.
3. Repair context builder.
4. Candidate patch model and null adapter.
5. Pre/postcondition draft generator.
6. Reproduction test model and hard-evidence rules.
7. Execution-free certificate model.
8. Gate runner (SARIF, build, test, interface gates).
9. Monitor hooks.
10. Patch selection policy.
11. Blast-radius stub.
12. Scope audit wiring.
13. Operational review pre-check.
14. `BugResolveReport` assembler.
15. Session trace manifest writer.
16. `run_issue_resolution` task-capable tool.
17. Full public `bug-resolve` prompt.
18. Private skill templates.

Reasoning:

- State machine must exist before any stage can be tested.
- Null adapter allows full workflow test before LLM integration.
- Gate runner must be solid before patch selection and recommendations.
- Report assembler must be complete before `run_issue_resolution` is wired up.

---

## 25. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 13 |
|---|---|
| Phase 14 - Implementation-check | `InvestigateResult` model (shared investigate pattern); `ExecutionFreeCertificate` schema; gate runner structure |
| Phase 15 - Blast radius | `BlastRadiusStub` replaced by full `BlastRadiusReport`; same interface |
| Phase 16 - Dynamic traces | `CandidatePatch` and `GateRunnerResult` as inputs to trace-augmented gate loop |
| Phase 17 - Memory | `SessionTraceManifest` and `WorkflowState` as trajectory record source; `ReproductionTestRecord` as outcome label |
| Phase 18 - Release gates | `BugResolveReport` with `HarnessConditionSheet`; full workflow T1 smoke regression |
| Phase 19 - Distribution | `run_issue_resolution` tool; `bug-resolve` prompt; all four private templates |

---

## 26. Exit Criteria Mapping

Source Phase 13 exit criterion:

- `run_issue_resolution(issue_text)` produces: ranked suspects, patch candidate, pre/postcondition draft, certificate, gate results, patch-risk verdict, blast-radius map, Harness Condition Sheet, run record / session trace reference, operational compliance verdict.

Concrete acceptance:

- All eleven output fields non-null (or `not_available` with explicit diagnostic) in `BugResolveReport`.
- Each field references a stored, hash-verified artefact.

Source Phase 13 exit criterion:

- Failed or uncertain gates produce a non-merge recommendation.

Concrete acceptance:

- Any hard gate failure: `recommendation: block`.
- SARIF gate failure: `recommendation: block`.
- Certificate `unsupported`: `recommendation: review-required` minimum.

Source Phase 13 exit criterion:

- DryRUN/actual mismatches are reported and must be resolved or accepted as explicit residual risk.

Concrete acceptance:

- `BugResolveReport.dryrun_mismatches_ref` references all mismatches.
- `uncertainty` field includes mismatch count and types.

Source Phase 13 exit criterion:

- Process-noncompliant, trace-incomplete, or budget-exhausted runs cannot recommend merge.

Concrete acceptance:

- All three workflow states produce `recommendation: block` or `recommendation: unknown`.
- Tests for each state.

Source Phase 13 exit criterion:

- Generated reproduction tests cannot count as hard evidence until they execute, fail on the pre-fix version for the expected reason, and pass or explainably change after the candidate patch.

Concrete acceptance:

- `generated_test_is_hard_evidence: true` requires `pre_fix_result: fail` AND `fails_for_expected_reason: true`.
- Test that passes pre-fix cannot set `generated_test_is_hard_evidence: true`.

---

## 27. Definition Of Done

Phase 13 is done when:

- The ten-stage state machine is implemented and tested.
- The investigate stage integrates Phase 9 fault localisation and Phase 8 repo-QA.
- The repair stage uses a null adapter that allows full pipeline testing without LLM.
- Reproduction tests require pre-fix failure for hard-evidence status.
- The execution-free certificate model is populated for every candidate.
- The gate runner enforces all deterministic block conditions.
- Monitor hooks fire for doom-loops, repeated failing gates, and budget limits.
- Patch selection uses multi-criterion ordering.
- Blast-radius stub produces partial report with `is_partial: true`.
- `BugResolveReport` contains all eleven required outputs.
- `run_issue_resolution` task-capable tool completes null-mode run.
- Process-noncompliant, trace-incomplete, and budget-exhausted runs cannot produce `merge-supporting`.
- Public `bug-resolve` prompt is fully implemented and snapshot-stable.
- All four private skill templates render with stable snapshots.
- Session trace manifest is written for every completed run.

---

## 28. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Doom-loop not detected | Workflow loops indefinitely on a difficult issue | Enforce `max_repair_loops` counter; transition to `failed` unconditionally at limit |
| Generated reproduction test counts as hard evidence without pre-fix failure | Overfitted patch appears valid | Gate `generated_test_is_hard_evidence` strictly on pre-fix fail; test in unit tests |
| Patch applied to registered repo root | Unintended file changes | Default `sandbox_only: true`; require explicit config override; HC2 path allowlist enforced |
| Report assembler skips field on exception | Partial report misleads reviewer | Required fields must be validated before report is stored; `null` is not acceptable for required fields |
| DryRUN mismatches silently excluded | Residual risk not communicated | All mismatches in `dryrun_mismatches_ref`; `uncertainty` field required |
| Budget exhaustion at mid-investigation | Incomplete investigate result fed to repair | Budget monitor emits event at 80% and hard-stop at 100%; `budget_exhausted` transition preserves partial artefacts |
| Blast-radius stub returns empty report | Impact not communicated | `is_partial: true` makes scope explicit; Phase 15 hardens the service |
| Operational run record not linked | Process-compliance unverifiable | Log missing run record as diagnostic; treat as `trace-incomplete` for recommendation |
| SARIF gate unavailable (no Phase 6 run) | Security-class patches not checked | Treat missing SARIF as `unknown` gate; include in report uncertainty; do not treat as `pass` |

---

## 29. Phase 13 Completion Report Template

When Phase 13 implementation is complete, report:

```text
Phase 13 completion report

Implemented:
- WorkflowConfig and state machine (10 stages):
- Investigate stage (FL + repo-QA):
- Repair context builder:
- CandidatePatch model and null adapter:
- Pre/postcondition draft generator:
- ReproductionTestRecord and hard-evidence rules:
- ExecutionFreeCertificate model:
- Gate runner (SARIF, build, test, interface):
- Monitor hooks (doom-loop, failing-gate, budget, stale-snapshot):
- Patch selection policy:
- BlastRadiusStub:
- Scope audit wiring:
- Operational review pre-check:
- BugResolveReport assembler:
- SessionTraceManifest writer:
- run_issue_resolution task-capable tool:
- bug-resolve prompt (full implementation):
- investigate template:
- repair template:
- blast-radius template:
- risk-classify template (refined):

Verification:
- Stage unit tests:
- Monitor hook tests:
- Full null-mode workflow tests:
- Gate failure tests:
- Budget-exhausted tests:
- Trace-incomplete tests:
- Prompt and template snapshot tests:

Exit criteria:
- run_issue_resolution produces all 11 required outputs:
- Gate failures produce non-merge recommendation:
- DryRUN mismatches reported in uncertainty:
- Process/trace/budget violations block merge-supporting:
- Reproduction tests require pre-fix failure for hard evidence:

Known limitations:
-

Follow-up for Phase 14:
-
```

---

## 30. Minimal First Slice Within Phase 13

If Phase 13 needs to be split further, implement this first:

1. `WorkflowConfig` model.
2. `WorkflowState` model and state machine skeleton (stages 1-3).
3. `InvestigateResult` model and investigate stage.
4. `RepairContextRecord` model and builder.
5. `CandidatePatch` model and null adapter.
6. `GateRunnerResult` model with SARIF and test gates.
7. Monitor hooks (doom-loop and budget only).
8. `BugResolveReport` model (partial).
9. `run_issue_resolution` null-mode task tool.
10. `bug-resolve` prompt (fully implemented from Phase 4 stub).
11. `investigate` template stub.
12. `repair` template stub.

This minimal slice makes end-to-end issue resolution usable by MCP clients in null mode, establishes the gate runner, and upgrades the Phase 4 `bug-resolve` prompt stub to a full implementation, all without requiring LLM integration.
