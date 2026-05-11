# LLM-SCA Tooling Phase 14 Implementation Plan: Implementation-Check Workflow

> Date: 2026-05-09
> Repository name: `evidence-sca`
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 14 - Implementation-Check Workflow
> Primary objective: determine whether the current implementation satisfies design/spec clauses — seven-stage DAG from document ingestion through executable contracts, graph grounding, static/dynamic verdicts, and calibrated aggregation; `run_implementation_check` tool; fully implemented `implementation-check` prompt; and `audit` template in implementation-check mode.

---

## 1. Phase Summary

Phase 14 is the implementation-compliance workflow phase of `evidence-sca`. Phases 1-13 built the index, SARIF layer, repo-QA, fault localisation, evaluation harness, patch review gates, SAST repair, and bug-resolve. Phase 14 adds the capability to check whether the code does what a design document, spec, or requirements file says it should do.

The central rule for this phase is:

```text
A design clause is not satisfied by LLM agreement alone.
`satisfied` requires: hard predicates pass AND graph/test/static or trusted
dynamic evidence supports the clause with calibrated confidence.
Hard predicate failures dominate soft positive evidence unconditionally.
`unknown` is preserved whenever evidence is missing, repo-QA is behaviour-tracing
only, graph links are ambiguous, or dynamic evidence is unavailable for a
runtime-only claim.
Behaviour-tracing repo-QA alone cannot auto-pass high-stakes checks until
graph-augmented swe-qa/coreqa behaviour accuracy reaches >=70%.
Stage-7 auto-pass requires ECE <=0.10 on the Vul4J calibration set or an
accepted local equivalent.
```

Phase 14 should implement:

- Spec/document ingestion (Markdown first; PDF/HTML later).
- Clause extraction and clause model.
- Harness-policy clause class.
- Structured intent graph.
- Clause-to-code grounding through document links, repo-QA, graph slices, and interface contracts.
- Contract artefact generation: Semgrep, CodeQL, pytest/unit tests, natural-language probes.
- Static verdict runner (stages 1-6a).
- Optional dynamic verdict hook (stage 6b).
- Stage-7 verdict aggregator with ECE gate.
- Clause verdict matrix.
- Operational evidence binding.
- Manifest and tool-description regression integration.
- `run_implementation_check` task-capable tool.
- Public `implementation-check` prompt (graduates from Phase 4 stub).
- Private `audit` template (implementation-check mode).

### Architecture Coverage

Phase 14 covers:

- F4 implementation-check.
- F11 run-record and policy/gate evidence for implementation-check verdicts.
- Public `implementation-check` prompt (fully implemented).
- Seven-stage implementation-check DAG (architecture §13.1).
- Private `audit` skill template (implementation-check mode).
- `run_implementation_check` tool.

Tools in this phase:

- `run_implementation_check`

Prompt graduated in this phase:

- `implementation-check` (from stub to full implementation)

Private skill template refined in this phase:

- `audit` (implementation-check mode, extending Phase 11's patch mode)

### Inherited Paper Anchors

Use these anchors in Phase 14 issues, ADRs, and implementation-check reports:

- `kgacg`
- `mids-valve`
- `jml-autodoc`
- `predicatefix`
- `codespecbench`
- `swe-qa`
- `coreqa`
- `repo-path-retrieval-llm`
- `swd-bench`
- `agent-coevo`

## Technology Stack

This phase uses the following libraries from `llm-sca-tooling-tech-stack.md`:

| Library/Tool | PyPI package | Version | Role in this phase |
|---|---|---|---|
| Python | — | 3.12+ | Runtime |
| uv | — | latest | Environment and dependency management |
| markdown-it-py | `markdown-it-py` | >=3.0 | **ACTIVATED** — Markdown spec/design-doc ingestion; clause extraction from `.md` files |
| lxml | `lxml` | >=5.2 | HTML spec document parsing via `lxml.html` |
| defusedxml | `defusedxml` | >=0.7 | XXE protection for any XML-based spec documents |
| Pydantic v2 | `pydantic` | >=2.0 | `Clause`, `HarnessPolicyClause`, `IntentGraph`, `ClauseGrounding`, `ClauseVerdictMatrix` schemas; `extra="forbid"` |
| orjson | `orjson` | >=3.10 | Verdict payload serialisation, clause matrix serialisation, all JSON I/O |
| FastMCP + FastAPI | `fastmcp`, `fastapi` | >=2.0, >=0.115 | `run_implementation_check` MCP tool handler |
| pytest + pytest-asyncio | `pytest`, `pytest-asyncio` | >=8.0, >=0.23 | Implementation-check tests; `asyncio_mode="auto"` |

- markdown-it-py is activated in this phase for Markdown spec ingestion; it was not used in prior phases.
- lxml/defusedxml are used for HTML spec documents; PDF ingestion is deferred to a later phase.
- All tool handlers and DAG stage functions are `async def`; subprocess calls (Semgrep/CodeQL contract execution) use `asyncio.create_subprocess_exec`.
- Rich is restricted to the CLI layer; all other modules use `logging`.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 14 depends on:

- Phase 1 schemas:
  - `ContractArtifact` model with `clause_id`, `language`, `artifact_type`, `target_symbols`, `source_clause_span`, `compile_status`, `last_run_status`, `confidence`
  - `Verdict` model with `satisfied`, `violated`, `unknown`, and ECE fields
  - `RunRecord` and `RunEvent` models
  - `HarnessConditionSheet` model
  - `IntentNode` and `DesignClause` graph node types
- Phase 2 stores:
  - graph store with `document`, `design_clause`, `intent_node`, `contract_artifact`, `predicate` node types
  - operational store
- Phase 4 infrastructure:
  - task manager
  - `implementation-check` prompt slot (upgrading from stub)
  - tool-description regression harness
- Phase 5 language backends:
  - AST-based symbol index for predicate compilation and SARIF execution
- Phase 6 SARIF layer:
  - `run_static_analysis` for Semgrep/CodeQL contract execution
- Phase 7 interface plugins:
  - interface contracts from `get_interface_contract`
- Phase 8 repo-QA:
  - `answer_repo_question` and `classify_repo_question` for stage-4 soft probe
  - ship-gate tracking (≥70% behaviour-tracing accuracy required for hard-evidence use)
- Phase 9 fault localisation:
  - `get_graph_slice` for clause-anchored graph context
- Phase 10 evaluation harness:
  - `HarnessConditionSheet` model
  - ECE bucket fields from `record_eval_result`
  - `codespecbench` adapter skeleton
- Phase 11 patch review:
  - `MaintainabilityGateResult` model
  - `ScopeAuditResult` for harness-policy clause checks
- Phase 12 SAST repair:
  - `AlertBinding` and `AlertClassification` for clause-level SARIF evidence
- Phase 13 bug-resolve:
  - `InvestigateResult` pattern (shared investigate → ground → verify loop)
  - `ExecutionFreeCertificate` schema reuse

### Phase Outputs

Phase 14 should produce:

- `SpecDocument` model and Markdown ingestion pipeline.
- `Clause` model with all required fields.
- `HarnessPolicyClause` model.
- `IntentGraph` model.
- `ClauseGrounding` model.
- `ContractArtifactGenerator` interface (Semgrep, CodeQL, test, NL probe).
- `StaticVerdictRecord` model and runner.
- `DynamicVerdictRecord` model and optional hook.
- `ClauseVerdictRecord` model and stage-7 aggregator.
- `ClauseVerdictMatrix` model.
- `OperationalEvidenceBinding` model.
- `ImplementationCheckReport` model.
- `run_implementation_check` task-capable tool handler.
- Fully implemented `implementation-check` public prompt.
- `audit` skill template (implementation-check mode).
- Implementation-check workflow tests.

### Non-Goals

Do not implement these in Phase 14:

- JML-like formal specification language parser (NL probes are the Stage 3 fallback; JML forms are backlog).
- PDF or HTML document ingestion (Markdown only in Phase 14).
- Full dynamic verdict integration (Phase 16 `capture_trace` provides this; Phase 14 includes only a hook).
- Cross-repo clause grounding (graph grounding is per-registered-repo in Phase 14).
- Trained clause-confidence calibration model (ECE gate uses placeholder until calibration data is produced by Phase 10).
- Blast-radius traversal for affected clauses (Phase 15 handles this).
- Memory hints for implementation-check (Phase 17).

---

## 3. Recommended File Layout

Assuming package name `evidence_sca`:

```text
src/evidence_sca/
  impl_check/
    __init__.py
    models.py
    ingestion.py
    clause_extractor.py
    harness_policy.py
    intent_graph.py
    grounding.py
    contract_generator.py
    static_verdict.py
    dynamic_verdict.py
    aggregator.py
    verdict_matrix.py
    operational_binding.py
    report.py

  mcp_server/
    tools/
      impl_check.py
    prompts/
      implementation_check.md

  skills/
    audit.md

tests/
  impl_check/
    fixtures/
      specs/
        simple_feature_spec.md
        security_spec.md
        harness_policy_spec.md
        ambiguous_spec.md
      contracts/
        semgrep_rule.yaml
        pytest_contract.py
      graphs/
        feature_graph_fixture.json
    test_ingestion.py
    test_clause_extractor.py
    test_harness_policy.py
    test_intent_graph.py
    test_grounding.py
    test_contract_generator.py
    test_static_verdict.py
    test_dynamic_verdict.py
    test_aggregator.py
    test_verdict_matrix.py
    test_operational_binding.py
    test_report.py
    test_run_implementation_check.py
    test_implementation_check_prompt.py
    test_audit_template.py
```

---

## 4. Seven-Stage Implementation-Check DAG

### 4.1 DAG Overview

The seven-stage DAG follows the architecture's `§13.1` design. Each stage refines the evidence for each clause:

| Stage | Name | Input | Output | Mode |
|---|---|---|---|---|
| 1 | Spec ingestion and clause parsing | Document text | `Clause` list | `[PY-CODE]` |
| 2 | Intent graph construction | Clauses | `IntentGraph` | `[PY-CODE]` + `[LLM]` |
| 3 | Executable contract generation | Clauses + symbols | `ContractArtifact` per clause | `[HYBRID]` |
| 4 | Clause-to-code grounding | Clauses + graph | `ClauseGrounding` | `[PY-CODE]` + `[HYBRID]` |
| 5 | Static verdict runner | Contracts + SARIF + tests | `StaticVerdictRecord` | `[PY-CODE]` |
| 6a | Graph-augmented repo-QA probe | Clauses + grounding | Soft `StaticVerdictRecord` | `[HYBRID]` |
| 6b | Dynamic verdict hook | Suspects + reproduction | `DynamicVerdictRecord` (optional) | `[HYBRID]` |
| 7 | Verdict aggregator | All stage outputs | `ClauseVerdictRecord` | `[PY-CODE]` + `[ML-MODEL]` |

### 4.2 Stage Ordering Rationale

Hard evidence must be evaluated before soft evidence:

- Stage 5 (static predicates) results are final if they produce `violated`.
- Stage 6a (repo-QA soft probe) can only add positive evidence, never override a Stage 5 violation.
- Stage 6b (dynamic trace, optional) can add hard dynamic evidence that can produce `violated`.
- Stage 7 fuses all signals with calibrated weights; `violated` from any hard stage is not reversible.

---

## 5. Stage 1: Spec Ingestion and Clause Parsing

### 5.1 `SpecDocument` Model

Required fields:

```text
SpecDocument
  doc_id
  source_path
  doc_format
  title
  content_hash
  ingested_ts
  clause_count
  provenance
```

### 5.2 `Clause` Model

Required fields:

```text
Clause
  clause_id
  doc_id
  text
  source_span
  scope
  priority
  checkability
  target_candidates
  risk_class
  rejected_interpretations
  parent_clause_id
  atomic
  harness_policy_flag
```

`checkability` values:

- `static`: can be verified by static analysis, predicate, or graph traversal.
- `dynamic`: requires runtime trace or test execution.
- `hybrid`: requires both static and dynamic evidence.
- `structural`: maintainability or architecture property.
- `unverifiable`: cannot be checked automatically; always produces `unknown`.

`risk_class` values (inherited from Phase 1 vocabulary):

- `security`
- `correctness`
- `performance`
- `compatibility`
- `maintainability`
- `compliance`
- `unknown`

### 5.3 Clause Extraction Interface

Clause extraction should:

1. Split document into sections.
2. Identify sentences that express requirements, obligations, or constraints (keywords: "must", "shall", "should", "must not", "is required to").
3. Attempt to split compound clauses into atomic sub-clauses.
4. Identify `target_candidates` (function names, class names, module paths) from the text.
5. Assign `clause_id` as a stable hash of `(doc_id, source_span)`.
6. Flag clauses that cannot be made atomic with `atomic: false`.
7. Preserve `rejected_interpretations` when a clause is ambiguous.

Rules:

- A clause that cannot be grounded is not dropped; it becomes `unknown` with a `missing_grounding` reason.
- Compound clauses that cannot be split are not split; they are marked `atomic: false`.
- The clause extractor must preserve source spans for every clause.

### 5.4 `HarnessPolicyClause` Model

A specialised clause for requirements expressed in `AGENTS.md`, runtime overlays, tool descriptions, and release gates:

Required additional fields:

```text
HarnessPolicyClause
  policy_source
  enforcement_mechanism
  checked_by_tool
  harness_stage_required
```

Harness-policy clauses must be checked against executable traces or deterministic gate outputs whenever possible. They have `harness_policy_flag: true`.

### 5.5 Tests

Required tests:

- Clause extractor produces atomic clauses for simple feature spec.
- Compound clause preserved as `atomic: false`.
- Ambiguous clause preserves rejected interpretations.
- Harness-policy clause extracted from `AGENTS.md` fixture.
- Clause ID is stable across repeated extractions of same span.

---

## 6. Stage 2: Intent Graph Construction

### 6.1 Purpose

The intent graph maps clauses to one another (parent/child, prerequisite, conflict), to symbols in the repository graph, and to test or SARIF evidence nodes. It is the navigational structure for grounding and verdict aggregation.

### 6.2 `IntentGraph` Model

Required fields:

```text
IntentGraph
  graph_id
  doc_id
  clause_ids
  intent_nodes
  decomposes_to_edges
  satisfies_edges
  violates_edges
  checks_edges
  snapshot_id
  created_ts
```

`IntentNode` (reuses Phase 1 graph node type `intent_node`):

```text
IntentNode
  node_id
  clause_id
  text_summary
  target_symbol_ids
  evidence_node_ids
  confidence
```

### 6.3 Intent Graph Population

Rules:

- Each `Clause` produces one or more `IntentNode` entries.
- `decomposes_to` edges link parent clauses to sub-clauses.
- `checks` edges link contract artefacts (Stage 3) to clause nodes.
- `satisfies` / `violates` edges are populated by the verdict runner (Stage 5+7).
- The intent graph is stored as graph nodes and edges in the Phase 2 graph store.

---

## 7. Stage 3: Executable Contract Generation

### 7.1 Purpose

Following the `kgacg`, `mids-valve`, `jml-autodoc`, and `predicatefix` patterns, Stage 3 generates machine-executable contracts for clauses that are `checkability: static` or `checkability: hybrid`.

### 7.2 Contract Types

| Type | Language | Generator | Compile check |
|---|---|---|---|
| `semgrep` | YAML rule | LLM + template | Semgrep dry-run |
| `codeql` | QL snippet | LLM + template | CodeQL compile |
| `pytest` | Python test | LLM + template | `py -m py_compile` |
| `unit_test` | Target language | LLM + template | Linter |
| `natural_language_probe` | English | Template fill | N/A |
| `jml_like` | Pseudo-JML | Future | Future |

### 7.3 `ContractArtifactGenerator` Interface

Recommended interface:

```text
ContractArtifactGenerator
  artifact_type
  generate(clause, grounding) -> ContractArtifact
  compile_check(artifact) -> CompileResult
```

### 7.4 `ContractArtifact` Model (Phase 1 reuse)

Required fields as specified in Phase 1:

```text
ContractArtifact
  clause_id
  language
  artifact_type
  target_symbols
  source_clause_span
  compile_status
  last_run_status
  confidence
```

`compile_status` values:

- `passed`
- `failed`
- `not_applicable`
- `not_attempted`

### 7.5 Rules

Rules:

- A contract artefact that fails to compile or lint is not hard evidence; it becomes a diagnostic.
- Natural-language probes have `compile_status: not_applicable`.
- The generator produces at most one artefact per clause per type; duplicate types for the same clause are merged, not stacked.
- Contracts are stored as graph nodes linked to their clause with `checks` edges.

### 7.6 Null Generator Adapter

For testing, a null contract generator produces deterministic contracts with `compile_status: not_attempted` and pre-canned `last_run_status` values. This allows full Stage 5-7 testing without running Semgrep or CodeQL.

---

## 8. Stage 4: Clause-to-Code Grounding

### 8.1 Purpose

Grounding maps each clause to specific repository artefacts: symbols in the graph, file paths, interface contracts, and document links. Ungrounded clauses are never dropped; they become `unknown`.

### 8.2 `ClauseGrounding` Model

Required fields:

```text
ClauseGrounding
  clause_id
  grounding_method
  symbol_node_ids
  file_node_ids
  graph_slice_refs
  interface_contract_ids
  document_link_node_ids
  repo_qa_answer_refs
  confidence
  ungrounded_reason
```

`grounding_method` values:

- `symbol_match`: clause text matched to symbol names in the graph.
- `document_link`: clause linked to an existing graph `document` node.
- `repo_qa`: Phase 8 `answer_repo_question` resolved a file or symbol.
- `interface_contract`: Phase 7 `get_interface_contract` provided the symbol.
- `ungrounded`: no grounding could be established.

### 8.3 Grounding Pipeline

1. Attempt symbol-name matching from `target_candidates` to graph node IDs.
2. If not matched: attempt `repo_qa` grounding via Phase 8.
3. If not matched: attempt document-link grounding via Phase 8.
4. If not matched: set `grounding_method: ungrounded` and `confidence: unknown`.

Rules:

- `repo_qa` grounding is only trusted with `confidence >= 0.7` for file-location questions and `confidence >= 0.7` for behaviour-tracing questions in the current period.
- Stale graph snapshot forces `confidence: heuristic` for all symbol groundings.
- Grounding results are stored in the intent graph as `checks` and `satisfies` edge candidates.

---

## 9. Stage 5: Static Verdict Runner

### 9.1 Purpose

Stage 5 executes compiled contracts and evaluates the output. A `violated` verdict from Stage 5 is final and cannot be reversed by Stage 6a or 6b soft evidence.

### 9.2 `StaticVerdictRecord` Model

Required fields:

```text
StaticVerdictRecord
  clause_id
  stage
  verdict
  evidence_type
  contract_artifact_id
  sarif_alert_ids
  test_result_ids
  graph_path_evidence
  confidence
  ece_bucket
  override_reason
```

`verdict` values (hard verdicts from Stage 5):

- `satisfied`
- `violated`
- `unknown`

### 9.3 Static Evidence Sources (Priority Order)

1. **Compiled Semgrep/CodeQL predicate fires**: `violated` with `confidence: analyser`.
2. **Compiled Semgrep/CodeQL predicate does not fire**: `satisfied` with `confidence: analyser`.
3. **Graph path traversal proves code path present**: `satisfied` with `confidence: parser`.
4. **Graph path traversal proves code path absent**: `violated` with `confidence: parser`.
5. **Pytest/unit test passes**: `satisfied` with `confidence: test`.
6. **Pytest/unit test fails**: `violated` with `confidence: test`.
7. **SARIF alert bound to clause target**: `violated` with `confidence: analyser` (for security/correctness clauses).
8. **No static evidence**: `unknown`.

### 9.4 Harness-Policy Clause Check

For `harness_policy_flag: true` clauses:

- Check against tool-description regression results from Phase 10 manifest regression adapter.
- Check against permission/policy gate records from Phase 4A operational store.
- A missing required gate event can produce `violated` (the harness policy requires the gate to have run and passed).

### 9.5 Tests

Required tests:

- Semgrep rule fires → `violated`.
- Semgrep rule does not fire → `satisfied`.
- Graph path absent → `violated`.
- Missing static evidence → `unknown`.
- Harness-policy clause produces `violated` when required gate event is absent.

---

## 10. Stage 6a: Graph-Augmented Repo-QA Probe

### 10.1 Purpose

Stage 6a uses Phase 8's `answer_repo_question` to ask targeted questions about clause-to-code binding. Answers are soft evidence; they can support but never override Stage 5 verdicts.

### 10.2 Probe Construction

For each unresolved or `unknown` clause from Stage 5:

1. Formulate a file-location question: "Which file implements [clause target]?"
2. Formulate a behaviour question: "Does [function/class] satisfy [clause text]?"
3. Call `classify_repo_question` and `answer_repo_question`.
4. Store answer as `StaticVerdictRecord` with `stage: 6a` and `confidence: llm`.

### 10.3 Confidence Rules for Stage 6a

Rules:

- File-location answers with `confidence >= 0.7`: can upgrade `unknown` → `satisfied` for `checkability: static` clauses IF graph grounding is also present.
- Behaviour-tracing answers: soft support only; cannot auto-pass high-stakes checks until behaviour-tracing accuracy reaches ≥70%.
- Security/privacy clauses must prefer static/data-flow evidence over NL answers; Stage 6a soft answers cannot produce `satisfied` for security clauses.

---

## 11. Stage 6b: Dynamic Verdict Hook

### 11.1 Purpose

Stage 6b is an optional hook for dynamic evidence from Phase 16's `capture_trace`. It is dormant in Phase 14 unless Phase 16 is available.

### 11.2 `DynamicVerdictRecord` Model

Required fields:

```text
DynamicVerdictRecord
  clause_id
  stage
  trace_run_id
  compressed_trace_ref
  verdict
  divergence_points
  confidence
  available
```

### 11.3 Phase 14 Behavior

In Phase 14, Stage 6b:

- Checks if Phase 16 `capture_trace` is available.
- If available and a reproduction script exists: executes `capture_trace` and stores `DynamicVerdictRecord`.
- If not available: stores `DynamicVerdictRecord` with `available: false` and `verdict: unknown`.

Rules:

- Dynamic trace evidence follows the same hard-override rule as static evidence.
- A compressed trace showing a contradicted behaviour claim produces `violated`.
- Non-reproducing traces are `unknown`, not `satisfied`.

---

## 12. Stage 7: Verdict Aggregator

### 12.1 Purpose

The Stage-7 aggregator fuses all stage outputs into a single per-clause verdict with calibrated confidence and ECE bucket.

### 12.2 `ClauseVerdictRecord` Model

Required fields:

```text
ClauseVerdictRecord
  clause_id
  final_verdict
  confidence
  ece_bucket
  stage_5_verdicts
  stage_6a_verdicts
  stage_6b_verdict
  dominant_evidence
  aggregation_method
  auto_pass_gate_passed
  calibration_family
  uncertainty_reason
```

### 12.3 Aggregation Rules

Aggregation priority (highest to lowest):

1. Any `violated` from Stage 5 (hard predicate, test, or SARIF) → final `violated`, dominates all soft evidence.
2. Any `violated` from Stage 6b (dynamic trace) → final `violated`.
3. `satisfied` from Stage 5 with `confidence: parser` or `analyser` → `satisfied` (eligible for auto-pass gate).
4. Mixed Stage 5 signals with no violation → `unknown` or `satisfied` depending on auto-pass gate.
5. Only Stage 6a soft evidence, no Stage 5 → `unknown` for high-stakes; `satisfied` only if auto-pass gate passed.

### 12.4 Auto-Pass Gate

Auto-pass requires:

- ECE ≤ 0.10 on the Vul4J calibration set or accepted local equivalent.
- `confidence >= analyser` from at least one Stage 5 signal.
- No Stage 5 or 6b `violated` signals.
- Clause `risk_class` is not `security` or `compliance` (these require stricter evidence).

If calibration data is absent: `auto_pass_gate_passed: false`; verdict becomes `unknown` if only soft evidence is present.

### 12.5 `ClauseVerdictMatrix` Model

Required fields:

```text
ClauseVerdictMatrix
  doc_id
  run_id
  clause_count
  satisfied_count
  violated_count
  unknown_count
  security_clause_verdicts
  harness_policy_verdicts
  per_clause_records
  overall_compliance_status
  created_ts
```

`overall_compliance_status` values:

- `compliant`: all clauses `satisfied`, no `violated`.
- `non_compliant`: any clause `violated`.
- `partially_compliant`: some `satisfied`, some `unknown`, none `violated`.
- `unknown`: all clauses `unknown`.

---

## 13. Operational Evidence Binding

### 13.1 Purpose

Each clause check must record which graph snapshot, resources, tools, and gates were used. This makes the verdict auditable and traceable.

### 13.2 `OperationalEvidenceBinding` Model

Required fields:

```text
OperationalEvidenceBinding
  run_id
  clause_id
  graph_snapshot_id
  resource_refs
  tool_calls
  gate_results
  stale_snapshot_flag
  mixed_snapshot_flag
  required_gate_events_present
  harness_condition_id
```

### 13.3 Rules

Rules:

- Stale or mixed snapshots force `unknown` for clauses that depend on graph topology.
- Missing required gate event forces `violated` or `unknown` for harness-policy clauses.
- All operational evidence bindings are stored as run events in the Phase 4A operational store.

---

## 14. `ImplementationCheckReport` Model

### 14.1 Required Fields

```text
ImplementationCheckReport
  report_id
  run_id
  harness_condition_id
  doc_id
  spec_document_ref
  intent_graph_ref
  clause_verdict_matrix_ref
  violated_clauses
  unknown_clauses
  satisfied_clauses
  security_clause_summary
  harness_policy_summary
  operational_compliance_verdict
  manifest_regression_verdict
  overall_verdict
  recommendation
  uncertainty
  session_trace_manifest_ref
  created_ts
```

`overall_verdict`:

- `compliant`: all clauses satisfied with calibrated evidence.
- `non_compliant`: any clause violated.
- `partially_compliant`: mixed satisfied/unknown with no violations.
- `unknown`: insufficient evidence for all clauses.

`recommendation` values:

- `merge-supporting`: `compliant` AND `process-compliant`.
- `review-required`: `partially_compliant` or security/harness-policy clauses `unknown`.
- `block`: `non_compliant`.
- `unknown`: insufficient evidence.

---

## 15. `run_implementation_check` Tool

### 15.1 Purpose

Execute the seven-stage implementation-check DAG for a spec document and return a typed verdict matrix.

### 15.2 Input

```text
spec
repos?
policy?
null_mode?
task?
```

`spec` accepts: file path (Markdown), inline text, or artefact reference.

### 15.3 Output

- `TaskCreateResult` for the implementation-check task.
- On completion: `ImplementationCheckReport` reference with `ClauseVerdictMatrix`.

### 15.4 Workflow

1. Create `RunRecord` and task.
2. Ingest spec document (Stage 1).
3. Extract clauses; flag harness-policy clauses.
4. Construct intent graph (Stage 2).
5. Generate contract artefacts (Stage 3; null mode uses null generator).
6. Ground clauses to code (Stage 4).
7. Run static verdict runner (Stage 5).
8. Run Stage 6a repo-QA probe for unresolved clauses.
9. If Phase 16 available and `dynamic_hook: true`: run Stage 6b.
10. Aggregate verdicts (Stage 7).
11. Bind operational evidence.
12. Check manifest/tool-description regression for behaviour-spec clauses.
13. Assemble `ImplementationCheckReport`.
14. Attach `HarnessConditionSheet`.
15. Store report artefact.
16. Return report.

### 15.5 Permissions

- Required mode: read/search for spec ingestion and graph grounding; execute for contract execution and test runners.
- Path scope: registered repos, workspace, and spec document path.
- Network: none.
- Side effect: writes contract artefacts, intent graph nodes, and operational records.

### 15.6 Tests

Required tests:

- Null-mode run for `simple_feature_spec.md`: produces `ClauseVerdictMatrix`.
- Hard predicate violation: `non_compliant` verdict.
- Security clause with only soft evidence: `unknown` (auto-pass gate blocks).
- All `unknown` spec: `overall_verdict: unknown`.
- Harness-policy clause without required gate event: `violated`.
- `HarnessConditionSheet` attached to every report.

---

## 16. Public `implementation-check` Prompt

### 16.1 Graduation from Stub

In Phase 4, the `implementation-check` prompt was a stub. Phase 14 replaces it with a full implementation that:

- Accepts `spec`, `repos?`, and `policy?` arguments.
- Describes the seven-stage DAG clearly.
- Lists all resources and tools the MCP client should expect to be called.
- States the verdict rules: `satisfied` requires hard evidence; `unknown` is preserved; `violated` dominates.
- States the behaviour-tracing ship-gate constraint (≥70% accuracy required for auto-pass of behaviour-tracing clauses).
- States the ECE gate constraint for auto-pass.
- Mentions `run_implementation_check` as the launcher.

### 16.2 Tests

Required tests:

- Prompt renders with all arguments.
- Snapshot stable.
- Prompt mentions `run_implementation_check`.
- Prompt states `violated` dominates soft evidence.
- Prompt states ECE gate requirement.

---

## 17. Private `audit` Template (Implementation-Check Mode)

### 17.1 Entry

`audit(mode="implementation_check", content="<spec or design text>")`.

### 17.2 Template Structure

The template instructs the agent to:

1. Call `run_implementation_check(spec)` as a task.
2. Poll to completion.
3. Read the `ClauseVerdictMatrix`.
4. For each `violated` clause: state the evidence and which predicate/test fired.
5. For each `unknown` clause: state what evidence is missing.
6. For security/harness-policy clauses: highlight explicitly.
7. State the overall compliance verdict.
8. State any manifest regression findings that contributed to `violated` verdicts.
9. Include `HarnessConditionSheet` reference.
10. Include the `run_id` for operational review.

### 17.3 Template Rules

Rules:

- Template must never claim `compliant` when any clause is `violated`.
- Template must list all `violated` clauses explicitly.
- Template must not suppress `unknown` clauses for security or harness-policy categories.
- Template snapshot must be stable.

---

## 18. Test Plan

### 18.1 Model Tests

Required:

- All Phase 14 models round-trip through JSON.
- Clause extraction produces stable `clause_id` for same span.
- `ClauseVerdictRecord` aggregation rules applied correctly.

### 18.2 Stage Tests

Required per stage:

- Stage 1: atomic clause extraction; compound clause preserved; harness-policy flag.
- Stage 2: intent graph nodes and edges populated.
- Stage 3: contract artefact generated; compile-failed artefact is diagnostic only.
- Stage 4: grounding by symbol match; grounding by repo-QA; ungrounded clause preserved.
- Stage 5: violated from predicate; satisfied from graph path; unknown from missing evidence.
- Stage 6a: soft evidence cannot override Stage 5 violated.
- Stage 6b: hook dormant without Phase 16; DynamicVerdictRecord has `available: false`.
- Stage 7: aggregation priority rules; auto-pass gate blocked without calibration.

### 18.3 Tool and Report Tests

Required:

- `run_implementation_check` null-mode task lifecycle.
- `ImplementationCheckReport` assembled with all required fields.
- Security clause without hard evidence: `unknown` not `satisfied`.
- Harness-policy clause without gate event: `violated`.
- Manifest regression finding propagated to report.

### 18.4 Prompt and Template Tests

Required:

- `implementation-check` prompt renders; snapshot stable.
- `audit` implementation-check mode renders; snapshot stable.
- Both templates include required constraint statements.

---

## 19. Work Packages

### P14.1 Clause Model and Ingestion

Build: `SpecDocument`, `Clause`, `HarnessPolicyClause` models; Markdown ingestion pipeline; clause extractor.

Acceptance: Clauses extracted from fixture spec with stable IDs.

### P14.2 Intent Graph

Build: `IntentGraph`, `IntentNode` models; graph population from clauses; `decomposes_to` edges.

Acceptance: Intent graph stored as graph nodes in Phase 2 store.

### P14.3 Contract Generator

Build: `ContractArtifactGenerator` interface; Semgrep, CodeQL, pytest, NL probe generators; null adapter; compile check.

Acceptance: Null-adapter generates artefacts; real Semgrep rule compiles.

### P14.4 Clause Grounding

Build: `ClauseGrounding` model; symbol-match, repo-QA, and document-link grounding pipeline.

Acceptance: Grounding produces typed result for each fixture clause.

### P14.5 Static Verdict Runner and Stage 6a

Build: `StaticVerdictRecord` model; static evidence evaluator; Stage 5 runner; Stage 6a probe integration.

Acceptance: Predicate fire → violated; missing evidence → unknown.

### P14.6 Stage 6b Hook and Stage 7 Aggregator

Build: `DynamicVerdictRecord` model; Phase 16 hook stub; `ClauseVerdictRecord` model; aggregator with priority rules and auto-pass gate.

Acceptance: Aggregation priority correct; auto-pass gate blocked without calibration.

### P14.7 Operational Binding, Report, and Tool

Build: `OperationalEvidenceBinding` model; `ClauseVerdictMatrix` model; `ImplementationCheckReport` assembler; `run_implementation_check` task-capable tool.

Acceptance: Null-mode run produces full report with matrix and HarnessConditionSheet.

### P14.8 Prompts and Templates

Build: Full `implementation-check` public prompt; `audit` template (implementation-check mode); snapshot tests.

Acceptance: Both render; snapshots stable.

---

## 20. Suggested Implementation Order

Recommended order:

1. Clause model and Markdown ingestion.
2. Clause extractor.
3. Harness-policy clause detector.
4. Intent graph model and population.
5. Contract artefact null adapter.
6. Clause grounding pipeline.
7. Static verdict runner (Stage 5).
8. Stage 6a repo-QA probe integration.
9. Stage 6b dynamic hook stub.
10. Stage-7 aggregator with auto-pass gate.
11. Clause verdict matrix assembler.
12. Operational evidence binding.
13. `ImplementationCheckReport` assembler.
14. `run_implementation_check` task-capable tool.
15. Full `implementation-check` public prompt.
16. `audit` template (implementation-check mode).

---

## 21. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 14 |
|---|---|
| Phase 15 - Blast radius | Clause-to-symbol grounding for clause-impact traversal |
| Phase 16 - Dynamic traces | Stage 6b dynamic verdict hook; compressed trace feeds back as `DynamicVerdictRecord` |
| Phase 17 - Memory | `ClauseVerdictRecord` as trajectory outcome; `ImplementationCheckReport.overall_verdict` for utility labelling |
| Phase 18 - Release gates | `ClauseVerdictMatrix` for compliance gate; ECE calibration from `codespecbench` runs; harness-policy clause checks |
| Phase 19 - Distribution | `run_implementation_check` tool; `implementation-check` prompt; `audit` template |

---

## 22. Exit Criteria Mapping

Source Phase 14 exit criterion:

- `run_implementation_check(spec)` returns clause-level `satisfied`, `violated`, or `unknown`.

Concrete acceptance: `ClauseVerdictMatrix` with per-clause verdict for all fixture spec clauses.

Source Phase 14 exit criterion:

- Ungrounded clauses are preserved as `unknown`, not dropped.

Concrete acceptance: Ungrounded fixture clause produces `unknown` with `ungrounded_reason`.

Source Phase 14 exit criterion:

- Hard predicate failures dominate soft positive evidence.

Concrete acceptance: Stage 5 `violated` fixture is not reversible by Stage 6a `satisfied` answer.

Source Phase 14 exit criterion:

- Stage-7 aggregator preserves calibrated confidence and ECE bucket per clause.

Concrete acceptance: `ClauseVerdictRecord.ece_bucket` non-null in report; auto-pass gate blocked when ECE data absent.

Source Phase 14 exit criterion:

- Manifest, permission, and verification-policy regressions can produce `violated` even when application tests pass.

Concrete acceptance: Harness-policy clause without required gate event → `violated` in fixture test.

Source Phase 14 exit criterion:

- Implementation-check reports include run record, harness condition, and operational compliance status.

Concrete acceptance: All three fields non-null in `ImplementationCheckReport`.

---

## 23. Definition Of Done

Phase 14 is done when:

- Clause extractor produces atomic clauses with stable IDs and preserved rejected interpretations.
- Harness-policy clauses are detected and checked against gate records.
- Intent graph is stored as graph nodes and edges.
- Contract artefacts compile before they become hard evidence.
- Clause grounding maps to symbol IDs, file paths, or interface contracts; ungrounded → `unknown`.
- Stage 5 produces `violated`/`satisfied`/`unknown` from static evidence.
- Stage 6a soft answers do not override Stage 5 `violated`.
- Stage 7 aggregator enforces priority rules and auto-pass gate.
- `ClauseVerdictMatrix` is produced for every run.
- `run_implementation_check` null-mode task tool completes with full report.
- Public `implementation-check` prompt is fully implemented and snapshot-stable.
- `audit` template (implementation-check mode) renders and is snapshot-stable.
- Security and harness-policy clauses cannot auto-pass on soft evidence alone.

---

## 24. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Clause extractor splits incorrectly | Evidence mapped to wrong symbol | Preserve rejected_interpretations; unit-test extractor on diverse spec fixtures |
| Hard predicate overridden by Stage 6a soft answer | Security violation masked | Aggregation rule: Stage 5 `violated` is final; test with fixture that has contradicting signals |
| Auto-pass gate applied without calibration | Unsupported `satisfied` verdicts | Gate requires ECE ≤ 0.10 on calibration set; default `false` when calibration absent |
| Harness-policy clause not detected | AGENTS.md compliance not checked | Explicit detection rule for policy sources; test with AGENTS.md fixture |
| Intent graph grows too large for grounding | Performance degradation | Limit intent graph to clauses from current spec; prune stale doc nodes |
| Repo-QA accuracy below ship gate | Behaviour-tracing answers given as hard evidence | Explicitly track behaviour-tracing accuracy; gate hard-evidence use on ≥70% accuracy |
| Stage 6b dynamic hook ignored silently | Dynamic evidence never used | Store `DynamicVerdictRecord` with `available: false` in every run; Phase 16 activates the hook |

---

## 25. Phase 14 Completion Report Template

When Phase 14 implementation is complete, report:

```text
Phase 14 completion report

Implemented:
- Spec ingestion (Markdown):
- Clause extractor (atomic + compound):
- Harness-policy clause detection:
- Intent graph construction:
- Contract generator (Semgrep/CodeQL/pytest/NL probe, null adapter):
- Clause grounding (symbol/repo-QA/document-link):
- Stage 5 static verdict runner:
- Stage 6a repo-QA probe:
- Stage 6b dynamic hook stub:
- Stage 7 verdict aggregator with auto-pass gate:
- Clause verdict matrix:
- Operational evidence binding:
- ImplementationCheckReport assembler:
- run_implementation_check task-capable tool:
- implementation-check prompt (full):
- audit template (implementation-check mode):

Exit criteria:
- run_implementation_check returns clause-level verdicts:
- Ungrounded clauses preserved as unknown:
- Hard predicate failures dominate:
- ECE bucket preserved per clause:
- Manifest/policy regressions produce violated:
- Report includes run record + harness condition + operational compliance:

Known limitations:
-
Follow-up for Phase 15:
-
```

---

## 26. Minimal First Slice Within Phase 14

If Phase 14 needs to be split further, implement this first:

1. `SpecDocument` and `Clause` models.
2. Markdown clause extractor.
3. Harness-policy clause detector.
4. `ClauseGrounding` model and symbol-match grounding.
5. `ContractArtifact` null generator.
6. `StaticVerdictRecord` model and Stage 5 runner.
7. `ClauseVerdictRecord` model and Stage-7 aggregator (without auto-pass).
8. `ClauseVerdictMatrix` model.
9. `ImplementationCheckReport` model (partial).
10. `run_implementation_check` null-mode task tool.
11. Full `implementation-check` public prompt.
