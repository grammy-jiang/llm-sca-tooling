# LLM-SCA Tooling Phase 17 Implementation Plan: Trajectory Memory and Experience Replay

> Date: 2026-05-09
> Repository name: `evidence-sca`
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 17 - Trajectory Memory and Experience Replay
> Primary objective: reuse prior investigations and repairs safely — schema-grounded trajectory storage, coarse-to-fine retrieval with misalignment guard, Agent-HER-style hindsight relabelling for failed trajectories, Evo-Memory-style eviction/retention, write-path validation, reviewed operational lesson promotion, and the `code-intelligence://memory/{repo}/trajectories` resource with `retrieve_memory`, `record_trajectory`, `memory_compact`, and `promote_operational_lesson` tools.

---

## 1. Phase Summary

Phase 17 is the memory phase of `evidence-sca`. Phases 1-16 produced structured evidence: graph index, SARIF, fault localisation, eval baseline, patch-review gates, SAST repair, bug-resolve, implementation-check, blast radius, and dynamic traces. Phase 17 makes this evidence accumulate safely so future workflow runs can learn from past ones without inheriting their errors.

The central rule for this phase is:

```text
Memory must never override current hard evidence.
A memory record is a hypothesis about what worked before, not a fact about
what will work now.
Exact project facts are retrieved through validated graph records, not
unconstrained prose inference.
Raw prompts, full traces, full command outputs, and full source files are
not durable memory by default.
Unreviewed operational lessons remain run artefacts; they are not retrieved
as durable memory until promoted through `promote_operational_lesson`.
Memory is opt-in per workspace.
```

Phase 17 should implement:

- Memory opt-in policy.
- Schema-grounded project-memory model: decisions, constraints, allowed commands, components, incidents, explicit unknowns, rejected options.
- Trajectory record schema and writer.
- Privacy and retention fields.
- Redaction and secret-scan pipeline on the write path.
- Write-path validation gates.
- Coarse retrieval for investigation.
- Fine retrieval for repair and review.
- Misalignment guard (high-similarity, low-utility rejection).
- Hindsight relabelling interface (Agent-HER).
- Eviction/retention policy (Evo-Memory: promote/demote/expire).
- Operational lesson promotion pipeline.
- `code-intelligence://memory/{repo}/trajectories` resource.
- `retrieve_memory`, `record_trajectory`, `memory_compact`, `promote_operational_lesson` tools.
- Memory ship-gate enforcement.

### Architecture Coverage

Phase 17 covers:

- F10 memory and replay.
- F11 reviewed operational lesson promotion.
- `code-intelligence://memory/{repo}/trajectories` resource.
- `retrieve_memory` tool.
- `record_trajectory` tool.
- `memory_compact` tool.
- `promote_operational_lesson` tool.
- H9 governed memory harness control.
- Memory ship gate: HER + eviction must beat success-only memory by ≥3 pp pass-rate at constant context budget on T2/T3 before memory hints default on.

### Inherited Paper Anchors

Use these anchors in Phase 17 issues, ADRs, and memory reports:

- `agent-her`
- `evo-memory`
- `memory-management-empirical`
- `graph-memory-rl`
- `c2f-grounded-memory`
- `reporepair`
- `predicatefix`
- `schema-grounded-memory`
- `ama-bench`
- `agentic-harness-engineering`

## Technology Stack

This phase uses the following libraries from `llm-sca-tooling-tech-stack.md`:

| Library/Tool | PyPI package | Version | Role in this phase |
|---|---|---|---|
| Python | — | 3.12+ | Runtime |
| uv | — | latest | Environment and dependency management |
| SQLModel + Alembic | `sqlmodel`, `alembic` | >=0.0.21, >=1.13 | Trajectory record storage with schema-grounded tables; every table change requires a migration |
| fastembed + sqlite-vec | `fastembed`, `sqlite-vec` | >=0.3, >=0.1 | Coarse retrieval via vector similarity for investigation hints |
| NetworkX | `networkx` | >=3.3 | Fine retrieval using graph IDs from stored trajectories; trajectory-to-symbol linking |
| orjson | `orjson` | >=3.10 | Trajectory serialisation, embedding cache entries, eviction metadata, all JSON I/O |
| Pydantic v2 | `pydantic` | >=2.0 | `TrajectoryRecord`, `ProjectMemoryRecord`, `EvictionPolicy`, `WritePath`, `MemoryOptInPolicy` schemas; `extra="forbid"` |
| FastMCP + FastAPI | `fastmcp`, `fastapi` | >=2.0, >=0.115 | `retrieve_memory`, `record_trajectory`, `memory_compact`, `promote_operational_lesson` tool handlers and memory resource |
| pytest + pytest-asyncio | `pytest`, `pytest-asyncio` | >=8.0, >=0.23 | Memory tests; `asyncio_mode="auto"` |

- `detect-secrets` scan is applied BEFORE persistence on the write path to redact secrets from every trajectory record before it is stored.
- SQLModel + Alembic are activated in this phase for durable trajectory storage; all schema changes require Alembic migrations.
- fastembed + sqlite-vec (active since Phase 9) provide coarse retrieval; NetworkX fine retrieval uses graph IDs stored alongside trajectory records.
- All tool handlers and memory-pipeline functions are `async def`; CPU-bound embedding and compaction use `loop.run_in_executor`.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 17 depends on:

- Phase 1 schemas:
  - `trajectory`, `issue_class`, `fl_decision`, `patch_class`, `outcome` graph node types
  - `RunRecord` and `RunEvent` models
  - `HarnessConditionSheet` model
  - incident and promotion candidate models
- Phase 2 stores:
  - graph store for trajectory-to-symbol node links (`fixed_by`, `warned_by`, `documents` edges)
  - operational store for run records and incident records
  - artefact registry for bounded snippet storage
- Phase 4 infrastructure:
  - task manager (for `memory_compact` as a task-capable operation)
  - resource routing for memory resource
- Phase 9 fault localisation:
  - `LocalisationResult` as the FL decision source for trajectory records
- Phase 10 evaluation harness:
  - T2/T3 harness for ship-gate measurement
  - `HarnessConditionSheet` for every memory read/write
- Phase 11 patch review:
  - `PatchRiskResult` as the patch-class source
  - `PatchReviewReport` for outcome labelling
- Phase 12 SAST repair:
  - `SASTRepairReport.verdict` as outcome
- Phase 13 bug-resolve:
  - `SessionTraceManifest` and `WorkflowState` as trajectory record sources
  - `ReproductionTestRecord` for outcome labelling
- Phase 14 implementation-check:
  - `ClauseVerdictMatrix.overall_verdict` as trajectory outcome
- Phase 15 blast radius:
  - `BlastRadiusReport.impact_groups` as trajectory context
- Phase 16 dynamic traces:
  - `TraceRunResult` as a trajectory evidence artefact reference (not inline content)

### Phase Outputs

Phase 17 should produce:

- `MemoryOptInPolicy` model.
- `ProjectMemoryRecord` model (schema-grounded project facts).
- `TrajectoryRecord` model.
- `PrivacyRetentionFields` model.
- `WritePath` validation pipeline.
- `RetrieverInterface` (coarse and fine modes).
- `CoarseRetriever` for investigation phase.
- `FineRetriever` for repair and review phases.
- `MisalignmentGuard`.
- `HindsightRelabellerInterface` (LLM boundary for relabelling).
- `NullHindsightRelabeller` (test double).
- `EvictionPolicy` model (Evo-Memory style).
- `MemoryCompactor`.
- `OperationalLessonPromotion` pipeline.
- `MemoryResource` handler.
- `retrieve_memory` tool handler.
- `record_trajectory` tool handler.
- `memory_compact` tool handler.
- `promote_operational_lesson` tool handler.
- Memory ship-gate reporter.
- Memory tests.

### Non-Goals

Do not implement these in Phase 17:

- Shared cross-user memory (memory is per workspace and per repo).
- Unrestricted prose memory (schema-grounded records only).
- Automatic lesson promotion without human review.
- Memory as hard evidence override (memory is always soft context).
- Memory from raw prompts, full traces, full command outputs, or full source files.
- Federated memory across organisations.
- Memory from runs that predate Phase 17 without explicit migration.

---

## 3. Recommended File Layout

Assuming package name `evidence_sca`:

```text
src/evidence_sca/
  memory/
    __init__.py
    policy.py
    models.py
    trajectory.py
    project_memory.py
    privacy.py
    write_path.py
    redaction.py
    retrieval/
      __init__.py
      interface.py
      coarse.py
      fine.py
      misalignment_guard.py
    relabelling/
      __init__.py
      interface.py
      null_relabeller.py
    eviction/
      __init__.py
      policy.py
      compactor.py
    promotion/
      __init__.py
      pipeline.py
      models.py
    ship_gate.py

  mcp_server/
    tools/
      memory.py
    resources/
      memory.py

tests/
  memory/
    fixtures/
      trajectories/
        successful_fix.json
        failed_fix.json
        false_positive_suppressed.json
        low_utility.json
      project_memory/
        project_decisions.json
        known_constraints.json
    test_policy.py
    test_trajectory.py
    test_project_memory.py
    test_privacy.py
    test_write_path.py
    test_redaction.py
    test_coarse_retriever.py
    test_fine_retriever.py
    test_misalignment_guard.py
    test_null_relabeller.py
    test_eviction_policy.py
    test_compactor.py
    test_promotion_pipeline.py
    test_record_trajectory.py
    test_retrieve_memory.py
    test_memory_compact.py
    test_promote_operational_lesson.py
    test_memory_resource.py
    test_ship_gate.py
```

---

## 4. Memory Opt-In Policy

### 4.1 `MemoryOptInPolicy` Model

Required fields:

```text
MemoryOptInPolicy
  workspace_id
  enabled
  per_repo_overrides
  retention_class_default
  max_trajectory_count
  max_project_memory_records
  allow_snippet_storage
  max_snippet_bytes
  allow_hindsight_relabelling
  allow_operational_lesson_promotion
  secret_scan_required
  pii_redaction_required
  review_required_for_promotion
  opt_in_ts
  opt_in_actor
```

### 4.2 Rules

Rules:

- Memory is disabled by default (`enabled: false`).
- Enabling memory requires an explicit opt-in with actor and timestamp.
- A disabled workspace rejects all `record_trajectory`, `retrieve_memory`, and `promote_operational_lesson` calls with a typed `MemoryDisabled` error.
- Per-repo overrides can disable memory for specific repos even when the workspace is enabled.
- `secret_scan_required: true` is the non-relaxable default; it cannot be disabled in the policy without a reviewed waiver.
- `review_required_for_promotion: true` is the non-relaxable default.

---

## 5. Schema-Grounded Project Memory

### 5.1 Purpose

Project memory stores durable facts about the project that inform future agent sessions — not session-specific context, but validated architectural decisions, known constraints, reviewed lessons, and explicit unknowns.

### 5.2 `ProjectMemoryRecord` Model

Required fields:

```text
ProjectMemoryRecord
  record_id
  repo_id
  record_type
  content_structured
  source_run_id
  source_event_id
  owner
  retention_class
  expiry_ts
  review_state
  contradiction_check_ts
  rollback_path
  created_ts
  updated_ts
```

`record_type` values (schema-grounded categories):

- `decision`: an architectural or design decision with rationale.
- `constraint`: a known limitation or requirement.
- `allowed_command`: a command that is explicitly approved for agent execution.
- `component`: a key component or module with ownership metadata.
- `incident`: a known past failure with root cause and containment.
- `explicit_unknown`: a stated area of uncertainty.
- `rejected_option`: a considered approach that was explicitly rejected with reason.

`review_state` values:

- `unreviewed`: newly written, not yet reviewed.
- `under_review`: being reviewed.
- `approved`: reviewed and approved for retrieval.
- `expired`: past expiry date.
- `superseded`: replaced by a newer record.

### 5.3 Rules

Rules:

- Only `approved` records are returned by `retrieve_memory`.
- `unreviewed` records are visible only to operators via operational review, not to agent workflows.
- `contradiction_check_ts` records when the record was last checked against current graph facts.
- Records that contradict current graph facts must be `superseded` before the contradiction propagates.
- Vague natural-language lessons must not be stored as `ProjectMemoryRecord`; only structured fields are accepted.

---

## 6. Trajectory Record

### 6.1 Purpose

A trajectory record stores the structured decisions and outcomes of one workflow run, linking them to graph nodes so future runs can retrieve similar prior cases.

### 6.2 `TrajectoryRecord` Model

Required fields:

```text
TrajectoryRecord
  trajectory_id
  repo_id
  workflow_type
  issue_class
  issue_text_hash
  fl_decisions
  graph_node_ids
  graph_snapshot_id
  patch_diff_hash
  patch_class
  sarif_delta_summary
  test_delta_summary
  outcome
  utility
  hindsight_label
  hindsight_label_confidence
  relabelled
  source_run_id
  source_trace_manifest_id
  retention_class
  expiry_ts
  review_state
  bounded_snippet_ids
  created_ts
```

`outcome` values:

- `resolved`: patch merged, all gates passed.
- `resolved_with_risk`: patch merged, remaining-risk notes present.
- `no_fix_found`: workflow could not produce a passing patch.
- `rejected_by_review`: patch produced but rejected during review.
- `false_positive`: SAST alert confirmed false positive.
- `uncertain`: outcome not definitively determined.
- `relabelled`: outcome was relabelled by hindsight (Agent-HER).

`utility` values:

- `high`: trajectory is highly relevant for future similar issues.
- `medium`: partially relevant.
- `low`: unlikely to provide useful hints.
- `unknown`: utility not yet computed.

### 6.3 `PrivacyRetentionFields` Model

Required fields:

```text
PrivacyRetentionFields
  retention_class
  expiry_ts
  source_run_id
  owner
  export_permitted
  delete_on_request
  rollback_path
  bounded_snippets_only
  raw_prompt_excluded
  full_trace_excluded
  command_output_excluded
  full_source_excluded
```

`retention_class` values:

- `ephemeral`: expires with the workspace session.
- `workspace_local`: retained until workspace is destroyed.
- `long_term`: retained until expiry date or explicit deletion.
- `archived`: retained for audit; not retrieved by default.

---

## 7. Write-Path Validation

### 7.1 Purpose

Every trajectory and project-memory write goes through a validation pipeline that checks required fields, data classification, secret scan, PII redaction, and contradiction against current records.

### 7.2 Write-Path Gates

Gates run in order:

1. **Opt-in check**: workspace memory enabled? If not: reject with `MemoryDisabled`.
2. **Required fields**: `source_run_id`, `graph_snapshot_id`, `repo_id` must be non-null.
3. **Data classification**: check `retention_class` against workspace policy.
4. **Secret scan**: run HC1 secret-scanner patterns over all string fields. Any match: reject with `SecretDetected`.
5. **PII redaction**: apply PII scrubber to `issue_text_hash` and `bounded_snippet_ids` content.
6. **Contradiction check**: compare `fl_decisions` and `graph_node_ids` against current graph. If contradiction detected: add diagnostic; do not block write; set `contradiction_check_ts`.
7. **Review state**: set `review_state: unreviewed` on write.

### 7.3 `WritePathResult` Model

Required fields:

```text
WritePathResult
  trajectory_id
  gates_passed
  gate_failures
  secret_detected
  contradiction_detected
  contradiction_detail
  review_state_set
  written
```

---

## 8. Retrieval

### 8.1 Coarse-to-Fine Pattern

Following `c2f-grounded-memory`:

- **Coarse retrieval** (investigation phase): issue-class and FL-class similarity. Returns `ProjectMemoryRecord` entries and trajectory IDs matching the issue class. Does not return full trajectory content.
- **Fine retrieval** (repair and review phases): concrete edit, predicate, test, or risk-pattern hints. Returns bounded snippets from matching trajectories, filtered by utility score and misalignment guard.

### 8.2 `RetrieverInterface`

```text
RetrieverInterface
  retrieve_coarse(issue_text, repo_id, phase) -> list[CoarseHint]
  retrieve_fine(issue_text, fl_result, repo_id, phase) -> list[FineHint]
```

### 8.3 `CoarseHint` Model

Required fields:

```text
CoarseHint
  trajectory_id
  issue_class
  outcome
  utility
  fl_class_match
  confidence
  rejected
  rejection_reason
```

### 8.4 `FineHint` Model

Required fields:

```text
FineHint
  trajectory_id
  hint_type
  content_snippet
  graph_node_ids
  patch_class
  outcome
  utility
  similarity_score
  misalignment_flag
  confidence
```

`hint_type` values:

- `fl_decision`: file-suspect ranking from a prior similar issue.
- `patch_snippet`: bounded code snippet from a successful repair.
- `predicate_example`: predicate/contract that previously fixed a similar alert.
- `risk_pattern`: patch-risk signal from a prior similar diff.
- `test_hint`: reproduction test that previously confirmed a similar fix.
- `rejection_reason`: documented reason a similar patch was rejected.

### 8.5 Misalignment Guard

The misalignment guard rejects records that are:

- **High similarity but low utility**: similarity score >= 0.85 AND `utility: low`. These records superficially match the current issue but historically provide no useful hints.
- **Expired**: past `expiry_ts`.
- **Unreviewed**: `review_state: unreviewed` (for `ProjectMemoryRecord`).
- **Superseded**: `review_state: superseded`.

Rejected records are returned to the caller as `CoarseHint.rejected: true` with `rejection_reason` — they are logged but not included in the active hints.

### 8.6 `retrieve_memory` Tool

Purpose: retrieve coarse-to-fine experience records for similar issue, FL, or patch classes.

Input:

```text
issue_text
phase: "investigate" | "repair" | "review"
repo?
fl_result_ref?
max_hints?
```

Output:

- List of `CoarseHint` or `FineHint` depending on `phase`.
- List of rejected records with rejection reasons.
- Memory availability status.

Rules:

- `phase: investigate` → coarse retrieval.
- `phase: repair` or `phase: review` → fine retrieval.
- Rejected records are always returned alongside active hints, never silently dropped.
- If memory is disabled: return `MemoryDisabled` status with empty hints.
- Memory hints are soft context; callers must not present them as hard evidence.

Permissions:

- Required mode: read/search.
- Path scope: workspace memory store.
- Network: none.
- Side effect: none.

---

## 9. Hindsight Relabelling (Agent-HER)

### 9.1 Purpose

Following `agent-her`, failed trajectories are not discarded. A trajectory where the patch failed to fix bug A may still demonstrate the correct repair pattern for a sibling bug B. Hindsight relabelling converts a failed goal-A trajectory into a useful demonstration for goal B.

### 9.2 `HindsightRelabellerInterface`

```text
HindsightRelabellerInterface
  relabel(trajectory, candidate_goal) -> HindsightLabel
  model_id
  version
```

### 9.3 `HindsightLabel` Model

Required fields:

```text
HindsightLabel
  trajectory_id
  original_outcome
  relabelled_goal
  relabelled_outcome
  relabelled_utility
  confidence
  evidence_refs
  generator_model
  review_state
```

### 9.4 `NullHindsightRelabeller`

For testing without LLM calls:

- Returns a deterministic `HindsightLabel` with pre-canned values.
- `confidence: unknown`.
- `generator_model: null`.

### 9.5 Rules

Rules:

- A relabelled trajectory is stored as a new `TrajectoryRecord` with `relabelled: true` and a reference to the original.
- The original trajectory is not modified.
- Relabelling requires `allow_hindsight_relabelling: true` in the memory policy.
- Relabelled trajectories have `review_state: unreviewed`; they enter the retrieval pool only after being promoted to `approved`.
- LLM relabelling output is stored as a labelled hypothesis, not a fact.

---

## 10. Eviction and Retention Policy (Evo-Memory)

### 10.1 Purpose

Following `evo-memory`, the memory compactor applies promote/demote/expire decisions to retained trajectories to keep the memory store high-quality over time.

### 10.2 `EvictionPolicy` Model

Required fields:

```text
EvictionPolicy
  max_trajectories_per_repo
  max_project_memory_per_repo
  utility_threshold_keep
  utility_threshold_demote
  recency_weight
  outcome_diversity_target
  issue_class_coverage_target
  relabelled_penalty
  expiry_default_days
  compaction_batch_size
```

### 10.3 Compaction Algorithm (Evo-Memory Style)

For each repo's memory store:

1. Compute utility score for each trajectory: `utility = f(outcome_success_rate, recency, issue_class_coverage, diversity_contribution)`.
2. Trajectories with `utility < utility_threshold_demote` → `utility: low`; mark for potential expiry.
3. Trajectories with `utility >= utility_threshold_keep` → `utility: high`; `promote`.
4. Apply `outcome_diversity_target`: ensure the retained set covers at least N distinct `outcome` classes.
5. Apply `issue_class_coverage_target`: ensure the retained set covers at least N distinct `issue_class` values.
6. Expire trajectories past `expiry_ts`.
7. If total count > `max_trajectories_per_repo`: remove lowest-utility records until within limit.

### 10.4 `memory_compact` Tool

Purpose: apply eviction/retention policy to trajectories for one or all repos.

Input:

```text
repo?
dry_run?
task?
```

Output:

- `MemoryCompactionReport` with: initial count, promoted count, demoted count, expired count, final count, utility distribution, outcome diversity achieved.

Permissions:

- Required mode: read/search (dry run) or execute (live compaction).
- Path scope: workspace memory store.
- Side effect: modifies utility and review-state fields; expires records.

---

## 11. Operational Lesson Promotion

### 11.1 Purpose

Following `schema-grounded-memory`, reviewed operational lessons from workflow runs can be promoted to durable memory, a detector, an eval regression case, a static-analysis rule update, a readiness task, or a governance policy change.

### 11.2 Promotion Gate

A lesson can be promoted only when:

1. Source `run_id` and `event_id` are linked.
2. A concrete, machine-checkable trigger condition is stated.
3. All required structured fields are present.
4. Owner and expiry/review date are set.
5. Rollback path is documented.
6. `review_required_for_promotion: true` is satisfied (human reviewer approved).

### 11.3 `OperationalLesson` Model

Required fields:

```text
OperationalLesson
  lesson_id
  source_run_id
  source_event_id
  trigger_condition
  lesson_type
  structured_content
  target_type
  owner
  expiry_ts
  review_date
  rollback_path
  review_state
  promoted_to_ref
  created_ts
```

`target_type` values:

- `memory`: promote to `ProjectMemoryRecord`.
- `detector`: promote to a monitor detector rule.
- `eval_regression`: add as an eval regression case.
- `static_analysis_rule`: candidate for offline rule evolution (Phase 12 `evolve_static_rules`).
- `readiness_task`: add to readiness checklist.
- `governance_policy`: propose change to `AGENTS.md` or related manifest.

### 11.4 `promote_operational_lesson` Tool

Purpose: convert a reviewed incident or repeated success into a typed durable record.

Input:

```text
source_run_id
source_event_id
target_type
structured_content
owner
expiry_ts
rollback_path
review_approved?
```

Output:

- `OperationalLesson` record.
- Reference to the promoted-to record if `target_type` requires creating a new record.

Rules:

- `review_approved: true` must be set by a human reviewer, not automatically by the workflow.
- Unreviewed lessons cannot be promoted; they remain as run artefacts.
- Promotions to `static_analysis_rule` or `governance_policy` must go through Phase 12's offline gate or a manifest change review respectively.

---

## 12. `record_trajectory` Tool

### 12.1 Purpose

Store a workflow trajectory linking issue, FL decisions, patch, gates, and outcome to graph nodes.

### 12.2 Input

```text
workflow_type
issue_text_hash
fl_decisions_ref
graph_node_ids
graph_snapshot_id
patch_diff_hash?
patch_class?
sarif_delta_summary?
test_delta_summary?
outcome
bounded_snippet_ids?
source_run_id
```

### 12.3 Output

- `WritePathResult` with gate outcomes.
- `TrajectoryRecord` if all gates pass.
- Rejected with `SecretDetected` or `MemoryDisabled` if gates fail.

### 12.4 Rules

Rules:

- `record_trajectory` must be called by Phase 13 Stage 10 (trajectory stage) automatically when memory is enabled.
- It may also be called by Phase 11, 12, 14 at their final report stage.
- The caller must not insert raw prompt text, full trace content, or source files as `bounded_snippet_ids`.
- `graph_node_ids` links the trajectory to specific symbols; this enables future graph-based retrieval.

### 12.5 Tests

Required tests:

- Successful write for fixture trajectory.
- Secret detected → `SecretDetected` rejection.
- Memory disabled → `MemoryDisabled` rejection.
- Missing `source_run_id` → rejected.
- Contradiction detected → written with diagnostic, not rejected.

---

## 13. `code-intelligence://memory/{repo}/trajectories` Resource

### 13.1 Payload

Payload should include:

- Trajectory count (total, by outcome class).
- Project memory record count.
- Last compaction timestamp.
- Utility distribution summary.
- Outcome diversity summary.
- Issue class coverage summary.
- Memory policy status (enabled/disabled).
- Last opt-in timestamp.
- Ship-gate status (HER+eviction vs. success-only memory).
- Unreviewed record count.

### 13.2 Rules

Rules:

- Resource does not return trajectory content; it returns aggregate metadata.
- Full trajectory content is accessed via artefact references.
- The resource is subscribable; `memory_compact` completion emits an update notification.

---

## 14. Memory Ship Gate

### 14.1 Purpose

Memory hints are enabled by default only after the ship gate passes: HER + eviction strategy must beat success-only memory by ≥3 pp pass-rate at constant context budget on the internal T2/T3 harness.

### 14.2 `MemoryShipGateResult` Model

Required fields:

```text
MemoryShipGateResult
  eval_run_id
  strategy_tested
  baseline_strategy
  pass_rate_strategy
  pass_rate_baseline
  delta_pp
  gate_passed
  context_budget_used
  harness_condition_id
  computed_ts
```

### 14.3 Rules

Rules:

- Until the gate passes: `retrieve_memory` returns hints but callers must treat them as `weight: 0` (zero-weight stub, same as Phase 9's memory stub default).
- The gate is evaluated on T2/T3 runs using Phase 10's eval harness.
- When the gate passes: update `MemoryOptInPolicy.enabled` for the workspace; log in `HarnessConditionSheet`.
- The gate must be re-evaluated if the memory strategy changes (new eviction policy, new retrieval model, or new relabelling model).

---

## 15. Test Plan

### 15.1 Model Tests

Required:

- All Phase 17 models round-trip through JSON.
- `TrajectoryRecord.outcome` enum exhaustive.
- `ProjectMemoryRecord.record_type` enum exhaustive.
- `OperationalLesson.target_type` enum exhaustive.

### 15.2 Write-Path Tests

Required:

- All five gates evaluated in order.
- Secret in string field → rejected.
- Memory disabled → rejected.
- Missing `source_run_id` → rejected.
- Contradiction detected → written with diagnostic.

### 15.3 Retrieval Tests

Required:

- Coarse retrieval returns matching trajectories by issue class.
- Fine retrieval returns snippets by FL class.
- Misalignment guard rejects high-similarity/low-utility record.
- Expired record not returned.
- Unreviewed `ProjectMemoryRecord` not returned.
- Rejected records appear in output with rejection reason.

### 15.4 Hindsight Relabelling Tests

Required:

- `NullHindsightRelabeller` produces deterministic label.
- Relabelled trajectory stored as new record with `relabelled: true`.
- Original trajectory unchanged.
- Relabelled record has `review_state: unreviewed`.

### 15.5 Eviction Tests

Required:

- Low-utility trajectories demoted below threshold.
- Diversity target maintained after compaction.
- Compaction report accurate.

### 15.6 Promotion Tests

Required:

- Unreviewed lesson rejected from promotion.
- Approved lesson promoted to `ProjectMemoryRecord`.
- `governance_policy` promotion requires manifest change review note.

### 15.7 Tool and Resource Tests

Required:

- `record_trajectory` write-path lifecycle.
- `retrieve_memory` coarse/fine modes.
- `memory_compact` dry-run and live.
- `promote_operational_lesson` approved and unapproved cases.
- Memory resource returns metadata payload.
- Ship-gate result computed.

---

## 16. Work Packages

### P17.1 Opt-In Policy and Schema-Grounded Project Memory

Build: `MemoryOptInPolicy` model; opt-in enforcement; `ProjectMemoryRecord` model with seven types; review-state model.

Acceptance: Disabled workspace rejects all memory operations.

### P17.2 Trajectory Record and Privacy/Retention

Build: `TrajectoryRecord` model; `PrivacyRetentionFields` model; retention-class enforcement.

Acceptance: Trajectory record with all required fields round-trips.

### P17.3 Write-Path Validation

Build: Five-gate pipeline; secret scanner integration; contradiction checker; `WritePathResult` model.

Acceptance: Secret detection rejects write; contradiction is logged without blocking.

### P17.4 Retrieval Infrastructure

Build: `RetrieverInterface`; `CoarseRetriever` (issue-class similarity); `FineRetriever` (FL-class + snippet); `CoarseHint` and `FineHint` models.

Acceptance: Coarse retrieval returns matching trajectories for fixture; fine retrieval returns snippets.

### P17.5 Misalignment Guard

Build: Misalignment-guard rules; similarity scoring placeholder; rejection-reason model.

Acceptance: High-similarity/low-utility fixture trajectory rejected by guard.

### P17.6 Hindsight Relabelling

Build: `HindsightRelabellerInterface`; `HindsightLabel` model; `NullHindsightRelabeller`; relabelled record writer.

Acceptance: Null relabeller produces deterministic label; relabelled record stored with correct fields.

### P17.7 Eviction/Retention Policy

Build: `EvictionPolicy` model; compaction algorithm (utility scoring, diversity target, issue-class coverage target); `MemoryCompactionReport` model.

Acceptance: Low-utility trajectories demoted; diversity target maintained.

### P17.8 Operational Lesson Promotion

Build: `OperationalLesson` model; promotion gate validation; `promote_operational_lesson` pipeline; target-type routing.

Acceptance: Unapproved lesson rejected; approved lesson promoted to `ProjectMemoryRecord`.

### P17.9 Tools and Resource

Build: `record_trajectory` tool; `retrieve_memory` tool; `memory_compact` task-capable tool; `promote_operational_lesson` tool; memory resource handler; update notification.

Acceptance: Full tool lifecycle for each tool; resource returns metadata payload.

### P17.10 Memory Ship Gate

Build: `MemoryShipGateResult` model; ship-gate evaluator using Phase 10 T2/T3 harness; weight-zero stub enforcement until gate passes.

Acceptance: Gate reports correct pass/fail; weight-zero enforced when gate not met.

---

## 17. Suggested Implementation Order

Recommended order:

1. Opt-in policy model and enforcement.
2. `ProjectMemoryRecord` model and review-state model.
3. `TrajectoryRecord` model and privacy/retention fields.
4. Write-path validation gates.
5. Secret scanner integration.
6. Contradiction checker.
7. `record_trajectory` tool.
8. `CoarseHint` and `FineHint` models.
9. `CoarseRetriever` (issue-class similarity).
10. `FineRetriever` (FL-class + snippet).
11. Misalignment guard.
12. `retrieve_memory` tool.
13. `NullHindsightRelabeller` and `HindsightLabel` model.
14. Eviction/retention policy and compactor.
15. `memory_compact` tool.
16. Operational lesson promotion pipeline.
17. `promote_operational_lesson` tool.
18. Memory resource handler.
19. Ship-gate evaluator.

---

## 18. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 17 |
|---|---|
| Phase 13 (upgrade) | `retrieve_memory` in Stage 1 (investigate); `record_trajectory` in Stage 10; memory hints at non-zero weight after ship gate passes |
| Phase 11 (upgrade) | Fine hints for patch-risk patterns in `classify_patch_risk` |
| Phase 12 (upgrade) | Fine hints for predicate examples and repair patterns |
| Phase 14 (upgrade) | Fine hints for similar clause-verdict history |
| Phase 18 - Release gates | Ship-gate result; memory governance H9 compliance; lesson promotion precision |
| Phase 19 - Distribution | `retrieve_memory`, `record_trajectory`, `memory_compact`, `promote_operational_lesson` tools; memory resource |

---

## 19. Exit Criteria Mapping

Source Phase 17 exit criterion:

- Workflows can record trajectories.

Concrete acceptance: Phase 13 `record_trajectory` call succeeds in null mode; `TrajectoryRecord` stored with all required fields.

Source Phase 17 exit criterion:

- `retrieve_memory(issue_text, phase)` returns useful hints plus rejected-memory notes.

Concrete acceptance: Fixture trajectory returned for matching issue class; misalignment-rejected trajectory appears in rejected list with reason.

Source Phase 17 exit criterion:

- Memory can be compacted deterministically.

Concrete acceptance: `memory_compact(dry_run=True)` returns `MemoryCompactionReport` without modifying records; live compaction demotes low-utility records.

Source Phase 17 exit criterion:

- Exact project facts are retrieved through validated records, not unconstrained prose inference.

Concrete acceptance: `ProjectMemoryRecord` retrieval is filtered to `review_state: approved`; records with unstructured `content_structured` fail write-path validation.

Source Phase 17 exit criterion:

- Memory updates are reviewable and rollbackable.

Concrete acceptance: Every `TrajectoryRecord` has `source_run_id` and `rollback_path`; `OperationalLesson` has `review_state` and `rollback_path`.

Source Phase 17 exit criterion:

- Unreviewed operational lessons remain run artefacts and are not retrieved as durable memory.

Concrete acceptance: `review_state: unreviewed` trajectory not returned by `retrieve_memory`; only `approved` records returned.

Source Phase 17 exit criterion:

- Raw prompts, full traces, full command outputs, and full source files are not durable memory.

Concrete acceptance: Write-path gate rejects artefact references of type `raw_prompt`, `full_trace`, or `full_source` in `bounded_snippet_ids`.

---

## 20. Definition Of Done

Phase 17 is done when:

- Memory opt-in policy is enforced; disabled workspace rejects all memory operations.
- `TrajectoryRecord` write-path validates five gates including secret scan.
- `ProjectMemoryRecord` is schema-grounded; unstructured prose fields fail validation.
- `retrieve_memory` returns coarse hints for investigation and fine hints for repair.
- Misalignment guard rejects high-similarity/low-utility records.
- Rejected records appear in output with rejection reasons.
- `NullHindsightRelabeller` allows full relabelling pipeline test without LLM.
- Relabelled trajectories stored as separate records with `review_state: unreviewed`.
- Eviction policy demotes low-utility and honours diversity targets.
- `memory_compact` dry-run produces accurate `MemoryCompactionReport`.
- `promote_operational_lesson` requires `review_state: approved` from human reviewer.
- Memory resource returns aggregate metadata (not trajectory content).
- Ship-gate evaluator produces `MemoryShipGateResult`; weight-zero enforced when gate not met.
- Raw prompts, full traces, and full source files rejected by write-path gate.

---

## 21. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Memory used as hard evidence | Wrong verdicts propagate from stale memory | Enforce `retrieve_memory` returns soft hints only; callers must not elevate to hard evidence; check in Phase 13 integration |
| Secret in trajectory content | HC1 violation | Write-path gate runs HC1 secret scanner; gate is non-relaxable; rejected records are logged, not silently dropped |
| Unreviewed lessons promoted automatically | Stale or incorrect policy propagates | `review_required_for_promotion: true` is non-relaxable; `promote_operational_lesson` requires `review_approved: true` set by human |
| Misalignment guard too aggressive | Useful trajectories filtered | Guard criteria: similarity ≥0.85 AND utility=low; threshold tunable; rejected records always visible in output |
| Compaction removes useful trajectories | Future retrieval quality degrades | Diversity and issue-class coverage targets protect minority cases; dry-run available; compaction report reviewed |
| Ship gate never passes | Memory hints permanently at zero weight | Ship gate uses T2/T3 harness; run regularly; if strategy is fundamentally inadequate, document and consider alternative |
| High-similarity trajectory relabelled incorrectly | Misleading fine hints | Relabelled records have `review_state: unreviewed`; not retrieved until approved; `NullRelabeller` for CI |
| Memory store grows unbounded | Storage and retrieval performance | `max_trajectory_count` per policy; compaction enforced; ship gate relies on bounded context budget |

---

## 22. Phase 17 Completion Report Template

When Phase 17 implementation is complete, report:

```text
Phase 17 completion report

Implemented:
- MemoryOptInPolicy:
- ProjectMemoryRecord (7 types):
- TrajectoryRecord:
- PrivacyRetentionFields:
- Write-path validation (5 gates):
- Secret scanner integration:
- Contradiction checker:
- CoarseRetriever:
- FineRetriever:
- MisalignmentGuard:
- NullHindsightRelabeller:
- EvictionPolicy and compactor:
- OperationalLesson promotion pipeline:
- record_trajectory tool:
- retrieve_memory tool:
- memory_compact tool:
- promote_operational_lesson tool:
- Memory resource:
- Ship-gate evaluator:

Exit criteria:
- Workflows can record trajectories:
- retrieve_memory returns hints + rejected notes:
- Memory compacted deterministically:
- Exact facts via validated records:
- Updates reviewable and rollbackable:
- Unreviewed lessons not retrieved:
- Raw prompts/traces/sources not stored:

Known limitations:
-
Follow-up for Phase 18:
-
```

---

## 23. Minimal First Slice Within Phase 17

If Phase 17 needs to be split further, implement this first:

1. `MemoryOptInPolicy` model and enforcement.
2. `TrajectoryRecord` model.
3. `PrivacyRetentionFields` model.
4. Write-path validation (secret scan and required-fields gates).
5. `record_trajectory` tool (basic write path).
6. `CoarseHint` model.
7. `CoarseRetriever` (issue-class similarity).
8. `retrieve_memory` tool (coarse mode only).
9. Misalignment guard (expired + unreviewed filter only).
10. Memory resource (metadata payload).
11. Ship-gate weight-zero stub enforcement.

This minimal slice makes trajectory recording and coarse retrieval available to Phase 13 workflows, establishes the secret-scan write gate, and enforces weight-zero for memory hints until the full ship gate is evaluated. Fine retrieval, hindsight relabelling, eviction, and promotion can follow in subsequent iterations.
