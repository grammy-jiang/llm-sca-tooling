# LLM-SCA Tooling Phase 1 Implementation Plan: Shared Schemas and Evidence Model

> Date: 2026-05-09
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 1 - Shared Schemas and Evidence Model
> Primary objective: implement the versioned, typed contracts that every later graph, MCP, workflow, operational, evaluation, memory, and release feature depends on.

---

## 1. Phase Summary

Phase 1 creates the shared schema layer for the LLM-SCA tooling package. It is not a storage, indexing, MCP, LLM, or workflow phase. It defines the typed contracts that make those later phases possible without collapsing repository evidence, LLM output, static-analysis findings, run traces, patch-risk judgments, and operational policy into loose prose.

The central rule for this phase is:

```text
No downstream feature can claim a fact, verdict, run outcome, policy decision, readiness score,
incident, or promotion unless Phase 1 has a typed model for that claim and a validator that can
reject malformed or under-provenanced data.
```

Phase 1 must preserve these principles from the source plan:

- Deterministic, typed, versioned evidence first.
- LLM output is only a hypothesis until validated by graph, static analysis, tests, traces, contracts, calibrated model evidence, or review.
- `unknown` is a valid verdict whenever evidence is stale, missing, ambiguous, uncalibrated, or operationally incomplete.
- Every graph fact must carry provenance and snapshot context.
- Every long-running task and workflow must be able to attach run events, policy decisions, budget events, verification results, redaction status, and a Harness Condition Sheet.
- Operational evidence is append-only, sequence-numbered, and reviewable.

### Architecture Coverage

Phase 1 covers the contract pieces of:

- F1 - Repository intelligence graph
- F0 - Harness quality substrate, where schema-backed controls are needed
- F11 - Operational harness, telemetry, and continuous improvement, at the model-contract level
- Shared evidence and verdict model
- Graph schema
- Contract artefact schema
- Patch, risk-finding, and verdict schema
- Run-record and operational-event schema
- Snapshot and provenance model
- Harness Condition Sheet model
- Harness stage, drift, readiness, policy, and supply-chain provenance models

### Inherited Paper Anchors

Use these anchors in implementation issues, ADRs, schema PR descriptions, and benchmark reports:

- `rig`
- `arise`
- `repograph`
- `codexgraph`
- `logiclens`
- `predicatefix`
- `codespecbench`
- `compass`
- `pvbench`
- `agenttrace`
- `aer`
- `opendev`
- `runtime-governance`
- `schema-grounded-memory`
- `agentic-harness-engineering`

Do not overuse paper anchors in source-code comments. Comments should explain non-obvious implementation choices, not reproduce the research registry.

## Technology Stack

Libraries directly used in Phase 1 implementation:

| Library | PyPI package | Version constraint | Purpose in this phase |
|---|---|---|---|
| Pydantic v2 | `pydantic` | `>=2.7` | All schema models; `model_config = ConfigDict(extra="forbid")` on every stable contract object |
| orjson | `orjson` | `>=3.10` | Primary JSON I/O: `orjson.dumps` / `orjson.loads` in serialization helpers, trace writers, and test fixtures |
| jsonschema | `jsonschema` | `>=4.23` | Validates raw JSON payloads against exported `.schema.json` files in round-trip and regression tests |
| jsf | `jsf` | `>=0.11` | Generates valid and invalid test fixtures from exported JSON Schema (dev dependency) |

### Critical conventions for this phase

- **No hand-written JSON Schema.** Every `.schema.json` file is exported from the Python source of truth via `model.model_json_schema()`. The `json_schema.py` helper calls this and writes the result deterministically.
- **`extra="forbid"` is the default.** Override only for explicit extension-point models (`attributes`, `properties`, `metadata`) and document the reason.
- **`orjson` everywhere.** Do not use `json.dumps` / `json.loads` in Phase 1 code. Use `orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)` for canonical output in test snapshots and schema exports.
- **`jsf` is a dev dependency only.** It is used in `tests/schemas/fixtures/` generation scripts; never imported from production code.
- **`jsonschema` validates cross-language contracts.** Use it in `test_json_schema_exports.py` to confirm exported files accept valid fixtures and reject invalid ones. Do not use it as the in-process model validator — Pydantic handles that.

---

## 2. Inputs, Outputs, and Boundaries

### Required Inputs

Phase 1 assumes Phase H0 and Phase 0 have established or planned these basics:

- A Python package skeleton.
- A `schemas` module location.
- A test runner.
- A local verify command.
- Basic configuration and structured error patterns.
- A trace/run-record writer skeleton, even if still file-based.
- A decision to use strict typed Python models and checked-in JSON Schema exports.

If Phase 0 is not fully implemented yet, Phase 1 can still define the file layout and schema documents, but implementation tasks should remain aligned with the intended package scaffold.

### Phase Outputs

Phase 1 should produce:

- Versioned JSON Schema files:
  - `graph.schema.json`
  - `run-record.schema.json`
  - recommended additional exported schema files listed in this document
- Python models for graph, evidence, verdicts, operations, governance, readiness, incidents, memory references, and supply-chain provenance.
- Validation helpers that reject malformed facts and under-provenanced evidence.
- Serialization and deserialization helpers.
- Round-trip tests.
- Invalid-input tests.
- Schema-regression tests for fields that affect manifests, tool descriptions, workflow gates, and release gates.
- Documentation explaining the model families, invariants, versioning, and downstream responsibilities.

### Non-Goals

Do not implement these in Phase 1:

- Graph storage.
- Repository registration.
- File scanning or indexing.
- MCP server routing.
- MCP task handling.
- SARIF parser or analyser execution.
- LLM calls.
- Embeddings.
- Patch generation.
- Workflow orchestration.
- Dynamic tracing.
- Memory retrieval.
- Evaluation benchmark runners.

Phase 1 should provide the contracts those later features use.

---

## 3. Recommended File Layout

Assuming the package name from Phase 0 is `llm_sca_tooling`, use a layout like this:

```text
schemas/
  graph.schema.json
  run-record.schema.json
  evidence.schema.json
  verdict.schema.json
  harness-condition.schema.json
  governance.schema.json
  readiness.schema.json
  incident.schema.json

src/llm_sca_tooling/
  schemas/
    __init__.py
    base.py
    provenance.py
    graph.py
    evidence.py
    sarif.py
    contracts.py
    patches.py
    verdicts.py
    run_records.py
    operations.py
    governance.py
    harness.py
    readiness.py
    incidents.py
    memory.py
    supply_chain.py
    validation.py
    json_schema.py

tests/
  schemas/
    fixtures/
      valid/
      invalid/
    test_base_models.py
    test_graph_schema.py
    test_evidence_schema.py
    test_verdict_schema.py
    test_run_record_schema.py
    test_governance_schema.py
    test_harness_condition_schema.py
    test_readiness_schema.py
    test_incident_schema.py
    test_json_schema_exports.py
    test_schema_regressions.py
```

If the project chooses a different package name, preserve the model boundaries and test coverage rather than the exact paths.

### Implementation Recommendation

Use Pydantic v2 or an equivalent strict validation layer for Python models, then export JSON Schema from the Python source of truth.

Recommended default:

- Strict top-level models.
- `extra="forbid"` for stable contract objects.
- Explicit `properties: dict[str, JsonValue]` extension fields only where controlled extensibility is required.
- UTC datetimes serialized as ISO-8601 strings.
- POSIX-style normalized relative paths for repository files.
- Canonical JSON output for test snapshots and schema exports.
- Stable enum values as lowercase strings.

---

## 4. Schema Versioning Policy

All exported schema documents and all persisted model payloads must include a schema version.

Recommended initial values:

```text
schema_family: graph | run-record | evidence | verdict | harness-condition | governance | readiness | incident
schema_version: 0.1.0
```

Versioning rules:

- Additive optional fields can bump patch version.
- New enum values can bump minor version when older consumers can safely treat them as unknown extensions.
- Removing fields, changing required fields, changing field meaning, or narrowing accepted values is a breaking change.
- During `0.x`, breaking changes should bump the minor version and include migration notes.
- Once `1.0.0` is declared, breaking changes must bump major version.
- Schema changes that affect manifests, tool descriptions, workflow gates, policy outcomes, or release gates require regression tests.

Each JSON Schema export should include:

- `$schema`
- `$id`
- `title`
- `description`
- `schema_family`
- `schema_version`
- `definitions` or `$defs`
- Strict required fields
- Reusable definitions for IDs, timestamps, provenance, snapshots, spans, artefact references, and confidence

---

## 5. Core Design Decisions

### Decision 1: Keep Provenance Separate But Mandatory

Every durable fact must reference a provenance object. The provenance object should be reusable by graph nodes, graph edges, evidence items, verdicts, run events, incidents, and promotion candidates.

This prevents later features from inventing separate provenance formats.

### Decision 2: Store Evidence Strength Separately From Confidence

`confidence` is not the same as evidence strength.

For example:

- A parser-derived `imports` edge can be hard static evidence with high confidence.
- An LLM-generated summary can have a high self-reported confidence but still be soft LLM evidence.
- A calibrated model result can support a verdict only within the calibration family recorded in the payload.

Phase 1 should model both:

- `confidence`: numeric or ordinal confidence.
- `evidence_strength`: hard static, hard dynamic, structured repository, calibrated model, or soft LLM.

### Decision 3: Preserve `unknown` As A First-Class Verdict

`unknown` is not a failure of the schema. It is the correct state when:

- Required evidence is missing.
- Evidence is stale.
- Snapshots are mixed.
- The only evidence is a summary or LLM explanation.
- The model is uncalibrated for the target family.
- Operational run evidence is incomplete.
- Redaction, permission, or budget policy prevents confident reconstruction.

### Decision 4: Operational Events Are Append-Only

Phase 1 should define models that allow Phase 2 and Phase 4A to implement append-only operational stores.

The schema must make it possible to validate:

- Monotonic event sequence numbers.
- Event-to-run ID consistency.
- Redaction status.
- Actor and stage.
- Policy action.
- Artefact references.
- Incident and promotion links.

### Decision 5: Strict Contract Models, Controlled Extension Points

Most schema objects should reject unknown top-level fields. Controlled extension should happen through explicit fields:

- `attributes`
- `properties`
- `metadata`
- `diagnostics`
- `capabilities`

This keeps the contract stable while allowing language backends, interface plugins, and future workflow features to attach additional structured data.

---

## 6. Base Primitives

Create these shared primitives before any domain-specific model.

### 6.1 IDs

Use stable string IDs with type-oriented prefixes where practical.

Recommended examples:

```text
repo_id: repo:<slug-or-hash>
node_id: node:<repo-id>:<stable-hash>
edge_id: edge:<repo-id>:<stable-hash>
artifact_id: art:<stable-hash>
run_id: run:<timestamp-or-ulid>
event_id: event:<run-id>:<seq-or-hash>
incident_id: incident:<timestamp-or-ulid>
verdict_id: verdict:<stable-hash>
snapshot_id: snap:<repo-id>:<stable-hash>
```

Validation requirements:

- IDs must be non-empty.
- IDs must be stable enough to survive serialization round trips.
- IDs must not include absolute local paths unless explicitly redacted and hashed.
- Long-running task IDs in later phases must be high entropy, but Phase 1 only needs to define compatible string fields.

### 6.2 Timestamps

Use UTC timestamp strings.

Recommended field names:

- `created_ts`
- `updated_ts`
- `start_ts`
- `end_ts`
- `ts`
- `review_due_ts`
- `expires_ts`

Validation requirements:

- `end_ts` cannot be earlier than `start_ts`.
- Event timestamps within a run should be non-decreasing when sequence validation has access to the whole run.
- Missing timestamps are allowed only for objects that are intentionally templates rather than records.

### 6.3 Repository References

Recommended model:

```text
RepoRef
  repo_id: string
  name: string | null
  root_ref: string | null
  remote_url_hash: string | null
  default_branch: string | null
```

Rules:

- `repo_id` is required for every durable fact.
- `root_ref` should not expose sensitive absolute paths in persisted artefacts unless the redaction policy allows it.
- Remote URLs should default to hashed or redacted form.

### 6.4 Snapshot References

Recommended model:

```text
SnapshotRef
  repo_id: string
  git_sha: string | null
  branch: string | null
  worktree_snapshot_id: string | null
  dirty: boolean
  index_status: fresh | stale | partial | mixed | unknown
  captured_ts: string
```

Rules:

- A clean committed snapshot should include `git_sha`.
- Dirty worktree evidence should include `worktree_snapshot_id`.
- Mixed-snapshot evidence must be representable and must force downstream `unknown` for audit-grade verdicts unless explicitly resolved.
- `index_status` must not default to `fresh` when unknown.

### 6.5 Source Spans

Recommended model:

```text
SourceSpan
  file_path: string
  start_line: int
  start_col: int | null
  end_line: int
  end_col: int | null
  byte_start: int | null
  byte_end: int | null
  encoding: string | null
```

Rules:

- `file_path` must be repo-relative.
- Line numbers are 1-based.
- `end_line` must be greater than or equal to `start_line`.
- Byte offsets are optional because not all tools provide them.
- Operational events can omit spans.

### 6.6 Artefact References

Recommended model:

```text
ArtifactRef
  artifact_id: string
  kind: graph_chunk | sarif | trace | diff | test_output | log | summary | report | schema | other
  uri: string
  sha256: string | null
  size_bytes: int | null
  media_type: string | null
  redaction_status: not_required | redacted | hash_only | blocked | unknown
  created_ts: string | null
```

Rules:

- Large outputs should be referenced by artefact ID and hash, not embedded in run events.
- `redaction_status` is required.
- `unknown` redaction status should block promotion to durable memory or release evidence until resolved.

### 6.7 Provenance

Recommended model:

```text
Provenance
  source_tool: string
  source_version: string | null
  source_run_id: string | null
  source_event_id: string | null
  repo: RepoRef
  snapshot: SnapshotRef
  file: string | null
  span: SourceSpan | null
  derivation: parser | analyser | build | test | trace | llm | heuristic | policy | review
  confidence: float
  evidence_strength: hard_static | hard_dynamic | structured_repository | calibrated_model | soft_llm
  created_ts: string
  attributes: object
```

Rules:

- `source_tool` is required.
- `repo` and `snapshot` are required for graph, code, SARIF, build, test, trace, patch, and verdict evidence.
- `file` and `span` are optional for operational events.
- `confidence` must be between 0.0 and 1.0.
- `derivation=llm` cannot have `evidence_strength=hard_static` or `hard_dynamic`.
- `evidence_strength=calibrated_model` requires calibration metadata on the consuming model output or verdict.
- Missing provenance must fail validation.

---

## 7. Enums

### 7.1 Graph Node Types

The graph node enum must match the architecture.

Repository structure:

- `repo`
- `package`
- `directory`
- `file`
- `module`

Code symbols:

- `class`
- `function`
- `method`
- `variable`
- `type`
- `interface`

Interface boundaries:

- `idl_interface`
- `http_route`
- `websocket_event`
- `grpc_service`
- `protobuf_message`

Specification and contracts:

- `document`
- `design_clause`
- `intent_node`
- `contract_artifact`
- `generated_test`
- `predicate`

Evidence:

- `test`
- `runtime_trace`
- `sast_rule`
- `sarif_alert`
- `build_target`
- `ci_job`
- `eval_run`

Change and review:

- `patch`
- `diff_hunk`
- `risk_finding`
- `verdict`

Memory:

- `trajectory`
- `issue_class`
- `fl_decision`
- `patch_class`
- `outcome`

Operational harness:

- `session`
- `run_record`
- `run_event`
- `harness_condition`
- `permission_profile`
- `tool_policy`
- `tool_call`
- `approval`
- `budget_event`
- `compaction_event`
- `monitor_alert`
- `incident`
- `readiness_score`
- `maintainability_oracle`
- `manifest_regression`

### 7.2 Graph Edge Types

Code and evidence edges:

- `contains`
- `imports`
- `calls`
- `dataflow`
- `tests`
- `documents`
- `decomposes_to`
- `checks`
- `satisfies`
- `violates`
- `implements`
- `exposes`
- `consumes`
- `ffi`
- `nullable`
- `owns`
- `instantiates`
- `warned_by`
- `fixed_by`
- `changed_by`
- `observed_in`

Operational edges:

- `used_tool`
- `approved_by`
- `denied_by`
- `verified_by`
- `blocked_by`
- `compacted_to`
- `promoted_to`
- `triggered_incident`

### 7.3 Derivation Types

- `parser`
- `analyser`
- `build`
- `test`
- `trace`
- `llm`
- `heuristic`
- `policy`
- `review`

### 7.4 Evidence Strength

Ordered from strongest to weakest for default verdict policy:

1. `hard_static`
2. `hard_dynamic`
3. `structured_repository`
4. `calibrated_model`
5. `soft_llm`

The ordering should be represented in code so workflow phases can compare evidence strength without hard-coding strings.

### 7.5 Verdict Values

Common verdict values:

- `satisfied`
- `violated`
- `safe`
- `risky`
- `unknown`
- `process-compliant`
- `process-noncompliant`
- `trace-incomplete`
- `budget-exhausted`
- `needs-readiness-work`

Workflow-specific extensions are allowed only through a controlled enum extension mechanism or a `workflow_verdict` field with validation.

### 7.6 Policy Actions

Recommended values:

- `allow`
- `deny`
- `approval_required`
- `blocked`
- `checkpoint`
- `force_unknown`
- `not_applicable`

### 7.7 Redaction Status

Recommended values:

- `not_required`
- `redacted`
- `hash_only`
- `blocked`
- `unknown`

### 7.8 Harness Stage And Drift

Harness stages:

- `S0`
- `S1`
- `S2`
- `S3`

Drift classifications:

- `missing`
- `stale`
- `relaxed`
- `out-of-stage`
- `clean`

---

## 8. Graph Schema

The checked-in `graph.schema.json` is the cross-language contract for all future indexing backends, interface plugins, SARIF binders, workflow outputs, memory records, and evaluation facts.

### 8.1 Graph Node

Recommended model:

```text
GraphNode
  schema_version: string
  node_id: string
  node_type: GraphNodeType
  label: string
  qualified_name: string | null
  repo: RepoRef
  snapshot: SnapshotRef
  file_path: string | null
  span: SourceSpan | null
  provenance: Provenance
  properties: object
  created_ts: string
```

Required validation:

- `node_id`, `node_type`, `repo`, `snapshot`, and `provenance` are required.
- `repo.repo_id` must match `snapshot.repo_id`.
- `file_path`, when present, must be repo-relative.
- Code symbol nodes should include either `qualified_name` or a deterministic local name in `properties`.
- Operational nodes can omit `file_path` and `span`.
- `provenance.derivation=llm` nodes must not be promoted as hard evidence without a later `verified_by` edge or stronger evidence.

### 8.2 Graph Edge

Recommended model:

```text
GraphEdge
  schema_version: string
  edge_id: string
  edge_type: GraphEdgeType
  source_id: string
  target_id: string
  repo: RepoRef
  snapshot: SnapshotRef
  provenance: Provenance
  confidence: float
  properties: object
  created_ts: string
```

Required validation:

- `source_id` and `target_id` are required and must be different unless an explicit self-edge type is later introduced.
- `edge_type`, `repo`, `snapshot`, and `provenance` are required.
- `confidence` must be between 0.0 and 1.0.
- Edge endpoints must exist when validating a complete graph document.
- Edge endpoint types should be checked where the phase has a known rule.
- Low-confidence or LLM-derived edges must not be silently treated as hard facts.

### 8.3 Graph Document

Recommended model:

```text
GraphDocument
  schema_family: graph
  schema_version: string
  graph_id: string
  repo: RepoRef
  snapshot: SnapshotRef
  generated_by: string
  generated_ts: string
  nodes: list[GraphNode]
  edges: list[GraphEdge]
  diagnostics: list[GraphDiagnostic]
  chunks: list[ArtifactRef]
```

Rules:

- A graph document can contain nodes and edges inline for small fixtures.
- Large production graphs should be represented by a manifest plus chunk references in later phases.
- `diagnostics` should make partial graph quality visible.
- Mixed-snapshot graph documents must be marked explicitly and must not pretend to be fresh.

### 8.4 Graph Diagnostic

Recommended model:

```text
GraphDiagnostic
  diagnostic_id: string
  severity: info | warning | error
  code: string
  message: string
  affected_node_ids: list[string]
  affected_edge_ids: list[string]
  provenance: Provenance | null
```

Examples:

- Parser backend missing.
- File skipped by ignore policy.
- Symbol binding failed.
- SARIF alert location could not be linked to a symbol.
- Mixed snapshot detected.
- Generated file detected.

### 8.5 Minimal Endpoint Compatibility Matrix

Phase 1 does not need a perfect ontology, but it should define enough endpoint checks to catch common data errors.

Recommended initial checks:

| Edge | Valid source examples | Valid target examples |
|---|---|---|
| `contains` | `repo`, `package`, `directory`, `file`, `module`, `class` | most structural or symbol nodes |
| `imports` | `file`, `module`, `package` | `file`, `module`, `package` |
| `calls` | `function`, `method` | `function`, `method` |
| `tests` | `test`, `generated_test` | `function`, `method`, `class`, `http_route`, `websocket_event` |
| `documents` | `document`, `design_clause` | code symbol, interface, contract, or evidence nodes |
| `decomposes_to` | `document`, `design_clause`, `intent_node` | `design_clause`, `intent_node` |
| `checks` | `contract_artifact`, `predicate`, `test`, `generated_test`, `sast_rule` | `design_clause`, code symbol, interface, or patch nodes |
| `satisfies` / `violates` | evidence, contract, verdict, trace, test, SARIF nodes | `design_clause`, `contract_artifact`, `patch`, `verdict` |
| `warned_by` | code symbol, file, route, interface | `sarif_alert`, `sast_rule` |
| `changed_by` | code, interface, contract, or graph node | `patch`, `diff_hunk` |
| `observed_in` | code symbol, route, interface | `runtime_trace`, `test`, `generated_test` |
| `used_tool` | `run_record`, `run_event`, `session` | `tool_call` |
| `approved_by` / `denied_by` | tool call, approval request, run event | approval, policy decision, reviewer event |
| `verified_by` / `blocked_by` | patch, verdict, run record, run event | verification, monitor, reviewer, gate result |
| `triggered_incident` | monitor alert, run event, reviewer decision | `incident` |

Endpoint validation can start conservative. Unknown future combinations should fail in strict mode and be allowed only when a declared schema extension says why.

---

## 9. Repository, File, Symbol, And Interface Models

These can be represented as graph nodes, but Python model helpers should make their expected properties explicit.

### 9.1 Repository Record

Recommended fields:

- `repo_id`
- `name`
- `root_ref`
- `default_branch`
- `registered_ts`
- `latest_snapshot`
- `capabilities`
- `metadata`

Do not implement repository persistence in Phase 1. Define the model that Phase 2 persists.

### 9.2 File Record

Recommended fields:

- `node_id`
- `repo`
- `snapshot`
- `path`
- `language`
- `size_bytes`
- `sha256`
- `is_generated`
- `is_test`
- `is_vendor`
- `encoding`
- `provenance`

Validation:

- `path` is repo-relative.
- `sha256` should be present when file content was read.
- `is_generated` should default to `false` only when detected or checked; otherwise use `unknown` or a diagnostic field.

### 9.3 Symbol Record

Recommended fields:

- `node_id`
- `symbol_type`
- `qualified_name`
- `display_name`
- `file_path`
- `span`
- `signature`
- `visibility`
- `language`
- `is_exported`
- `is_generated`
- `provenance`

Validation:

- Symbols require a file and span unless generated by an external analyser that lacks location data.
- Missing location must be represented as a diagnostic or low-confidence fact.

### 9.4 Interface Record

Recommended fields:

- `interface_id`
- `plugin_id`
- `interface_type`
- `name`
- `producer_nodes`
- `consumer_nodes`
- `contract_refs`
- `schema_refs`
- `confidence`
- `status`
- `provenance`
- `attributes`

Suggested `interface_type` values:

- `http_rest`
- `websocket`
- `idl`
- `grpc`
- `protobuf`
- `ffi`
- `other`

Rules:

- Exact interface links and ambiguous candidates must be distinguishable.
- Generated artefacts should be marked so later workflows avoid recommending manual edits to generated stubs.

---

## 10. SARIF Reference Model

Phase 1 does not parse SARIF. It defines references to SARIF runs and alerts.

Recommended models:

```text
SarifRunRef
  sarif_run_id: string
  repo: RepoRef
  snapshot: SnapshotRef
  analyzer_name: string
  analyzer_version: string | null
  ruleset: string | null
  artifact_ref: ArtifactRef | null
  provenance: Provenance

SarifAlertRef
  alert_id: string
  sarif_run_id: string
  rule_id: string
  predicate_id: string | null
  severity: error | warning | note | none | unknown
  level: string | null
  locations: list[SourceSpan]
  bound_node_ids: list[string]
  confidence: float
  provenance: Provenance
```

Rules:

- Preserve analyser name, analyser version, rule ID, predicate ID where available, severity, locations, and provenance.
- If symbol binding fails, keep the file/span alert and attach a diagnostic.
- SARIF alerts are evidence; they are not automatically verdicts.

---

## 11. Contract Artefact Model

Any `contract_artifact` produced by implementation-check, SAST repair, or patch review must carry:

```text
ContractArtifact
  artifact_id: string
  clause_id: string
  language: string
  artifact_type: jml | codeql | semgrep | pytest | unit_test | natural_language_probe
  target_symbols: list[string]
  source_clause_span: SourceSpan | null
  compile_status: not_run | passed | failed | skipped | unknown
  last_run_status: not_run | passed | failed | skipped | unknown
  confidence: float
  provenance: Provenance
  artifact_ref: ArtifactRef | null
  diagnostics: list[GraphDiagnostic]
```

Validation:

- `clause_id`, `artifact_type`, `target_symbols`, `compile_status`, `last_run_status`, and `provenance` are required.
- `natural_language_probe` is soft evidence unless later verified by a deterministic or calibrated process.
- A contract artefact cannot become hard evidence until it compiles, lints, or otherwise passes the appropriate validation for its type.

---

## 12. Patch, Risk Finding, And Verdict Models

### 12.1 Patch Record

Recommended fields:

- `patch_id`
- `diff_id`
- `repo`
- `base_snapshot`
- `target_snapshot`
- `changed_files`
- `changed_symbols`
- `diff_artifact`
- `generated_by_run_id`
- `provenance`
- `attributes`

Rules:

- Patches are not verdicts.
- Patches should be linked to diff hunks and changed symbols where available.
- Generated patches must retain source run and event references.

### 12.2 Risk Finding

Recommended fields:

- `finding_id`
- `diff_id`
- `changed_symbols`
- `sarif_delta_id`
- `test_delta_id`
- `risk_class`
- `calibrated_probability`
- `ece_bucket`
- `policy_action`
- `evidence_bundle_id`
- `provenance`
- `uncertainty`

Recommended `risk_class` values:

- `safe`
- `correct-but-overfit`
- `vulnerable`
- `vulnerability-introducing`
- `risky`
- `unknown`

Rules:

- A bare LLM label cannot be a risk finding.
- `safe` requires deterministic gate support in later phases.
- `unknown` is required when calibration metadata is missing for the relevant language or rule family.

### 12.3 Verdict

Recommended model:

```text
Verdict
  verdict_id: string
  workflow: string
  subject_ref: string
  verdict: VerdictValue
  confidence: float
  evidence_bundle_id: string
  run_record_id: string | null
  reasoning_chain: list[ReasoningStep]
  uncertainty: list[Uncertainty]
  recommended_action: string
  policy_action: PolicyAction
  calibration: CalibrationRef | null
  provenance: Provenance
```

Recommended `ReasoningStep` fields:

- `step_id`
- `claim`
- `evidence_refs`
- `strength`
- `limitations`

Recommended `Uncertainty` fields:

- `kind`
- `description`
- `affected_refs`
- `forces_unknown`

Validation:

- `verdict`, `confidence`, `evidence_bundle_id`, `recommended_action`, and `provenance` are required.
- `confidence` must be between 0.0 and 1.0.
- A non-`unknown` positive verdict cannot be supported only by `soft_llm` evidence.
- `unknown` verdicts should include uncertainty reasons.
- `process-noncompliant`, `trace-incomplete`, and `budget-exhausted` must be representable as final workflow verdicts.

---

## 13. Evidence Bundle Model

Evidence bundles let workflows return auditable verdicts without embedding large artefacts directly.

Recommended model:

```text
EvidenceBundle
  bundle_id: string
  subject_ref: string
  evidence_items: list[EvidenceItem]
  missing_evidence: list[MissingEvidence]
  stale_evidence: list[StaleEvidence]
  aggregate_strength: EvidenceStrength
  snapshot_consistency: clean | dirty | stale | mixed | unknown
  created_ts: string
  provenance: Provenance
```

Recommended `EvidenceItem` fields:

- `evidence_id`
- `kind`
- `supports`
- `refs`
- `artifact_refs`
- `strength`
- `confidence`
- `provenance`
- `notes`

Recommended `supports` values:

- `supports`
- `contradicts`
- `neutral`
- `context`

Rules:

- Evidence bundles should separate supporting, contradicting, contextual, missing, and stale evidence.
- Mixed or stale evidence must be visible.
- Evidence items should cite graph nodes, SARIF alerts, tests, traces, interface records, contract artefacts, memory records, or artefacts by ID.

---

## 14. Run Record And Run Event Schema

The run-record model is the foundation for operational review, trace replay, budget analysis, incidents, and memory promotion.

### 14.1 Run Record

Required fields from the source plan:

- `run_id`
- `workflow`
- `user_intent_hash`
- `repos`
- `start_ts`
- `end_ts`
- `status`
- `model_backend`
- `toolset_hash`
- `policy_id`
- `permission_profile`
- `context_budget`
- `run_event_count`
- `harness_condition_id`
- `final_verdict_id`
- `incident_ids`
- `redaction_policy`

Recommended model:

```text
RunRecord
  schema_family: run-record
  schema_version: string
  run_id: string
  workflow: implementation-check | bug-resolve | patch-review | operational-review | readiness-audit | eval | graph-build | graph-update | other
  user_intent_hash: string
  repos: list[RepoRef]
  start_ts: string
  end_ts: string | null
  status: created | running | blocked | failed | completed | cancelled | unknown
  model_backend: ModelBackendRef | null
  toolset_hash: string
  policy_id: string
  permission_profile: string
  context_budget: ContextBudget
  run_event_count: int
  harness_condition_id: string
  final_verdict_id: string | null
  incident_ids: list[string]
  redaction_policy: RedactionPolicy
  artifact_refs: list[ArtifactRef]
  created_ts: string
```

Rules:

- A run without a Harness Condition Sheet is incomplete for workflow/release evidence.
- `run_event_count` must match the event list when validating a complete record.
- Completed runs should have `end_ts`.
- Failed, blocked, cancelled, or budget-exhausted runs must preserve events up to the stopping point.

### 14.2 Run Event

Required fields from the source plan:

- `event_id`
- `run_id`
- `seq`
- `ts`
- `type`
- `actor`
- `stage`
- `input_ref`
- `output_ref`
- `policy_action`
- `token_count`
- `wall_ms`
- `artefact_ids`
- `redaction_status`

Recommended model:

```text
RunEvent
  schema_family: run-record
  schema_version: string
  event_id: string
  run_id: string
  seq: int
  ts: string
  type: RunEventType
  actor: user | agent | tool | policy | system | reviewer | monitor
  stage: string
  input_ref: string | null
  output_ref: string | null
  policy_action: PolicyAction | null
  token_count: int | null
  wall_ms: int | null
  artefact_ids: list[string]
  redaction_status: RedactionStatus
  payload: object
```

Recommended event types:

- `session_start`
- `session_end`
- `harness_condition_recorded`
- `stage_started`
- `stage_completed`
- `context_loaded`
- `context_compacted`
- `tool_call_started`
- `tool_call_completed`
- `tool_call_failed`
- `approval_requested`
- `approval_granted`
- `approval_denied`
- `policy_decision`
- `budget_warning`
- `budget_hard_stop`
- `verification_started`
- `verification_completed`
- `monitor_alert`
- `incident_opened`
- `incident_updated`
- `incident_closed`
- `promotion_candidate_created`
- `reviewer_decision`
- `final_verdict_recorded`

Validation:

- `seq` must be positive and unique within a run.
- Complete-run validation should require monotonic `seq`.
- `run_id` must match the owning run.
- Tool events should reference a tool-call payload.
- Approval events should reference approval payloads.
- Budget events should reference budget payloads.
- Redaction status is required for every event.

### 14.3 Session Trace

Recommended model:

```text
SessionTrace
  trace_id: string
  run_id: string | null
  session_start_ts: string
  session_end_ts: string | null
  events: list[RunEvent]
  artifact_refs: list[ArtifactRef]
  redaction_policy: RedactionPolicy
```

Rules:

- Session traces can exist before full workflow records.
- A session trace used as release evidence must link to a run record.
- Raw prompts, full source files, and full command output should not be durable trace content unless policy explicitly allows it.

---

## 15. Operational Event Payload Models

Run events should use typed payloads for common event families.

### 15.1 Tool Call Event

Recommended fields:

- `tool_call_id`
- `tool_name`
- `arguments_hash`
- `argument_artifact_ref`
- `scope`
- `side_effect_class`
- `permission_mode`
- `network_required`
- `policy_decision_id`
- `status`
- `result_ref`
- `retry_count`
- `token_count`
- `wall_ms`
- `provenance`

Rules:

- Tool arguments should be hashed or redacted where needed.
- A denied tool call should still produce an event.
- Side effects must be explicit.

### 15.2 Approval Or Denial Event

Recommended fields:

- `approval_id`
- `requested_action`
- `requested_by`
- `decision`
- `decided_by`
- `reason`
- `scope`
- `ts`
- `related_tool_call_id`
- `provenance`

Recommended `decision` values:

- `approved`
- `denied`
- `expired`
- `not_required`

### 15.3 Budget Event

Recommended fields:

- `budget_event_id`
- `budget_kind`
- `limit`
- `used`
- `unit`
- `threshold`
- `action`
- `reason`
- `checkpoint_ref`
- `provenance`

Budget kinds:

- `tokens`
- `tool_calls`
- `retries`
- `wall_clock_ms`
- `artifact_bytes`
- `trace_bytes`
- `context_items`

Rules:

- Budget hard stops should be modelled as first-class events.
- Budget hard stops should force `unknown`, checkpoint, or block according to policy.

### 15.4 Compaction Event

Recommended fields:

- `compaction_event_id`
- `source_artifact_refs`
- `summary_artifact_ref`
- `removed_evidence_refs`
- `retained_evidence_refs`
- `reason`
- `loss_assessment`
- `forces_unknown`
- `provenance`

Rules:

- Compaction must link to source artefacts.
- If compaction removes evidence needed for an audit-grade verdict, downstream verdicts must become `unknown` or require review.

### 15.5 Monitor Alert

Recommended fields:

- `alert_id`
- `alert_type`
- `severity`
- `run_id`
- `event_ids`
- `description`
- `policy_action`
- `incident_id`
- `provenance`

Initial alert types:

- `repeated_identical_tool_calls`
- `repeated_failing_gate`
- `context_growth_without_new_evidence`
- `denied_operation_storm`
- `budget_exhaustion`
- `stale_or_mixed_snapshot`
- `out_of_scope_write_attempt`
- `missing_required_verification`
- `secret_or_redaction_failure`
- `cumulative_risk_placeholder`

---

## 16. Permission, Policy, And Governance Models

### 16.1 Tool Permission

Recommended fields:

- `tool_name`
- `required_mode`
- `path_scope`
- `network_requirement`
- `side_effect_class`
- `approval_requirement`
- `allowed_stages`
- `deny_reason`

Permission modes:

- `read`
- `search`
- `edit`
- `execute`
- `review`
- `commit`

Side-effect classes:

- `none`
- `read_only`
- `writes_repo`
- `writes_outside_repo`
- `executes_code`
- `network`
- `destructive`
- `release`

### 16.2 Policy Decision

Recommended fields:

- `policy_decision_id`
- `policy_id`
- `run_id`
- `event_id`
- `tool_name`
- `requested_action`
- `decision`
- `reasons`
- `required_approval`
- `path_scope_result`
- `network_result`
- `side_effect_result`
- `stage_result`
- `provenance`

Rules:

- Policy enforcement is deterministic.
- LLM summaries can explain a policy violation but cannot waive it.
- Denied actions must be recorded.

### 16.3 Manifest Precedence Record

Recommended fields:

- `manifest_state_id`
- `repo`
- `canonical_manifest_ref`
- `runtime_overlay_refs`
- `skill_refs`
- `effective_policy_hash`
- `precedence_order`
- `non_relaxation_result`
- `drift_findings`
- `provenance`

Rules:

- `AGENTS.md` is the canonical project policy when present.
- Runtime overlays may specialize but cannot relax canonical policy.
- Relaxed drift must be representable as a blocking result.

### 16.4 Hard Constraint Model

Recommended fields:

- `constraint_id`
- `name`
- `description`
- `severity`
- `applies_to`
- `check_type`
- `policy_action`
- `source_manifest_ref`

Baseline hard constraints:

- HC1: no plaintext secrets in repo, prompts, logs, or commits.
- HC2: no writes outside the repository or path allowlist.
- HC3: explicit human approval for destructive commands.
- HC4: no agent-executed irreversible migrations.
- HC5: deny-by-default network egress.
- HC6: no red-class data in prompts, tool arguments, or logs.

---

## 17. Harness Condition Sheet Model

Every benchmark report, workflow run, release gate, and operational review should be able to include a compact Harness Condition Sheet.

Recommended model:

```text
HarnessCondition
  harness_condition_id: string
  run_id: string | null
  captured_ts: string
  runtime: RuntimeRef
  model_backend: ModelBackendRef | null
  manifest_hashes: list[ManifestHash]
  toolset_hash: string
  exposed_tools: list[ToolPermission]
  permission_profile: string
  sandbox: SandboxDescriptor
  network_policy: string
  context_policy: ContextBudget
  retry_policy: RetryPolicy
  verification_gates: list[VerificationGate]
  telemetry_location: string
  redaction_policy: RedactionPolicy
  sampling_capability: supported | unsupported | unknown
  supply_chain_refs: list[string]
  provenance: Provenance
```

Required sections:

- Runtime and model/backend.
- Manifest revision or hashes.
- Exposed tools.
- Permission mode.
- Sandbox and network policy.
- Verification gates.
- Context and cost policy.
- Retry policy.
- Telemetry location.
- Redaction policy.

Rules:

- A workflow run without a harness condition is operationally incomplete.
- Sampling availability should be recorded even before patch-review uses it.
- Supply-chain references should point to version/provenance records.

---

## 18. Verification And Maintainability Models

### 18.1 Verification Event

Recommended fields:

- `verification_id`
- `run_id`
- `gate_name`
- `gate_type`
- `command_ref`
- `status`
- `started_ts`
- `ended_ts`
- `artifact_refs`
- `summary`
- `policy_action`
- `provenance`

Gate types:

- `format`
- `lint`
- `typecheck`
- `unit_test`
- `integration_test`
- `sast`
- `secrets`
- `dependency_scan`
- `contract`
- `maintainability`
- `manifest_regression`
- `prompt_regression`
- `custom`

Rules:

- Skipped gates require reasons.
- Failing required gates must be able to block positive verdicts.

### 18.2 Maintainability Oracle Result

Recommended fields:

- `oracle_result_id`
- `run_id`
- `oracle_name`
- `status`
- `findings`
- `affected_refs`
- `policy_action`
- `provenance`

Initial oracle dimensions:

- Change locality.
- Dependency direction.
- Responsibility decomposition.
- Reuse of existing abstractions.
- Side-effect isolation.
- Testability.

### 18.3 Prompt Or Manifest Regression Result

Recommended fields:

- `regression_result_id`
- `run_id`
- `target_ref`
- `case_id`
- `case_type`
- `expected_behavior`
- `actual_behavior_ref`
- `status`
- `policy_action`
- `provenance`

Case types:

- `visible_behavior`
- `hidden_policy`
- `tool_order`
- `semantic_mutation`
- `spec_evolution`

---

## 19. Readiness, Drift, And Stage Models

### 19.1 Harness Stage Assessment

Recommended fields:

- `assessment_id`
- `repo`
- `stage`
- `detected_controls`
- `missing_controls`
- `next_stage_controls`
- `blocking_findings`
- `provenance`

Stage definitions:

- `S0`: greenfield baseline.
- `S1`: walking skeleton with tests/lint in CI and basic governance.
- `S2`: growing repo with tool DAG, schema-grounded memory controls, scans, maintainability gate, and readiness score in CI.
- `S3`: production with held-out evals, adversarial sweeps, provenance ledger, incidents, and governed harness evolution.

Rules:

- Stage upgrades are monotonic.
- Later stages can add or specialize controls but cannot weaken lower-stage controls.

### 19.2 Drift Finding

Recommended fields:

- `drift_id`
- `target_ref`
- `classification`
- `severity`
- `description`
- `blocks_release`
- `recommended_action`
- `provenance`

Classifications:

- `missing`
- `stale`
- `relaxed`
- `out-of-stage`
- `clean`

Rules:

- `relaxed` drift blocks release and higher-autonomy work unless reviewed.
- `clean` findings should still include evidence.

### 19.3 AI-Readiness Report

Recommended fields:

- `readiness_report_id`
- `repo`
- `stage`
- `total_score`
- `axis_scores`
- `threshold_result`
- `no_regression_result`
- `missing_controls`
- `waivers`
- `history_refs`
- `provenance`

Axes:

- `agent_config`
- `documentation`
- `ci_cd`
- `code_structure`
- `security`

Score rules from the source plan:

- Total score range is 0 to 25.
- Each axis should have a bounded score, recommended 0 to 5.
- `S0 -> S1` needs 5 total and at least 1 per axis.
- `S1 -> S2` needs 12 total and at least 2 per axis.
- `S2 -> S3` needs 18 total and at least 3 per axis.
- Stable `S3` needs 22 total and at least 4 per axis.
- A readiness-axis drop fails unless tied to an explicit reviewed waiver or incident.

### 19.4 Readiness Axis History

Recommended fields:

- `history_id`
- `repo`
- `axis`
- `previous_score`
- `current_score`
- `delta`
- `source_report_id`
- `waiver_id`
- `incident_id`
- `provenance`

---

## 20. Incident And Promotion Models

### 20.1 Incident

Recommended fields:

- `incident_id`
- `severity`
- `status`
- `title`
- `impact`
- `timeline`
- `root_cause`
- `containment`
- `remediation`
- `evidence_links`
- `source_run_ids`
- `source_event_ids`
- `detector_follow_up`
- `eval_follow_up`
- `reviewer`
- `closed_ts`
- `provenance`

Common incident types:

- Repeated loop.
- Out-of-scope write attempt.
- Secret exposure.
- Unsafe command request.
- Verification bypass.
- Stale-index verdict.
- Unreviewed memory write.
- Budget hard stop.

Rules:

- Incidents must link back to source run or event IDs.
- P0/P1 incidents should require detector or eval follow-up in later phases.
- Closed incidents require reviewer metadata.

### 20.2 Promotion Candidate

Recommended fields:

- `promotion_id`
- `source_run_id`
- `source_event_ids`
- `target_type`
- `target_ref`
- `lesson_summary`
- `review_state`
- `owner`
- `expires_ts`
- `rollback_path`
- `evidence_links`
- `provenance`

Target types:

- `memory`
- `detector`
- `eval_regression`
- `static_analysis_rule`
- `readiness_task`
- `governance_policy`

Rules:

- Unreviewed prose memory is rejected.
- Promotion candidates must retain source links, owner, expiry or review date, and rollback path.
- Promotion is not the same as durable memory. Phase 17 decides when reviewed candidates become retrievable memory.

---

## 21. Memory Reference Models

Phase 1 should not implement memory retrieval or compaction, but it must define enough schema surface for later trajectories.

### 21.1 Trajectory Reference

Recommended fields:

- `trajectory_id`
- `repo`
- `issue_ref`
- `source_run_id`
- `fl_decision_refs`
- `graph_slice_refs`
- `patch_ref`
- `sarif_delta_ref`
- `test_result_refs`
- `outcome_ref`
- `utility`
- `retention`
- `provenance`

Rules:

- Trajectories must link to source run evidence.
- Low-utility trajectories must be representable so retrieval can reject them later.

### 21.2 Retention Policy

Recommended fields:

- `retention_class`
- `expires_ts`
- `review_due_ts`
- `owner`
- `exportable`
- `delete_supported`
- `redaction_status`
- `rollback_path`

Rules:

- Raw prompts, full traces, full command outputs, and full source files are not durable memory by default.
- Memory records should store bounded snippets or artefact references unless explicit reviewed policy allows more.

---

## 22. Supply-Chain Provenance Model

Supply-chain provenance is part of the harness quality substrate and should be modelled early.

Recommended fields:

- `supply_chain_record_id`
- `component_type`
- `name`
- `version`
- `source`
- `hash`
- `signature`
- `lockfile_ref`
- `license`
- `scanner_result_refs`
- `captured_ts`
- `provenance`

Component types:

- `runtime`
- `mcp_server`
- `language_backend`
- `analyser`
- `prompt_asset`
- `skill`
- `dependency`
- `benchmark`
- `ruleset`

Rules:

- Analyzer, language backend, MCP server, prompt, skill, and dependency versions must be reportable.
- Lockfile or tool-manifest changes should be able to cite dependency and secret-scan evidence.

---

## 23. Serialization And Validation Helpers

### 23.1 Required Helpers

Implement helpers for:

- Model to canonical JSON.
- JSON to model.
- Model to JSON Schema.
- JSON Schema export to `schemas/`.
- Graph document validation.
- Run record plus event sequence validation.
- Evidence bundle validation.
- Verdict validation.
- Snapshot consistency validation.
- Provenance completeness validation.
- Redaction status validation.
- Schema version compatibility checks.

### 23.2 Canonical JSON Rules

Recommended canonicalization:

- Sort object keys.
- Use stable enum string values.
- Use UTC timestamp strings.
- Exclude Python-only fields.
- Preserve explicit `null` only where null has contract meaning.
- Do not serialize absolute paths unless redaction policy allows them.

### 23.3 Validation Modes

Recommended modes:

- `strict`: reject unknown fields and unknown enum values.
- `compat`: accept known-compatible older schema versions and migrate or warn.
- `fixture`: allow explicit test-only conveniences but never for release evidence.

---

## 24. Cross-Model Invariants

Phase 1 should implement these invariants as direct validators or as validation helper functions.

### Provenance Invariants

- Every graph node, graph edge, evidence item, verdict, run event payload, incident, promotion candidate, and readiness report has provenance.
- Every code-related fact has `repo` and `snapshot`.
- Every graph fact can carry `repo`, `git_sha`, optional `worktree_snapshot_id`, `file`, `span`, `confidence`, and `derivation`.
- Missing provenance fails validation.

### Snapshot Invariants

- Evidence from mixed snapshots is detectable.
- Dirty worktree evidence has a `worktree_snapshot_id`.
- Stale or mixed evidence can force `unknown`.
- Graph slices returned to downstream consumers must include snapshot references.

### Evidence Invariants

- LLM-derived evidence is soft unless verified by stronger evidence.
- A non-`unknown` positive verdict cannot be supported only by soft LLM evidence.
- Hard static evidence can directly fail a verdict when provenance is clear.
- Hard dynamic evidence can pass or fail behavior claims when environment provenance is trusted.
- Calibrated model evidence requires calibration metadata.

### Operational Invariants

- Run events are append-only and sequence-numbered.
- Run event `run_id` values match the owning run.
- Redaction status is required.
- Denied policy decisions are recordable and cannot disappear.
- Budget hard stops are recordable and can force `unknown`.
- Incidents and promotion candidates reference source run/event IDs.

### Policy Invariants

- `relaxed` drift is blocking unless reviewed.
- Missing required verification can block a positive workflow verdict.
- Out-of-scope writes, unauthorized network, destructive actions without approval, and redaction failures must be representable as process failures.

### Readiness Invariants

- Total readiness score is 0 to 25.
- Axis scores stay within the axis range.
- No-regression checks can compare current and previous reports.
- Waivers must be explicit and reviewed.

---

## 25. Example Payloads

These examples are intentionally small. Test fixtures should include richer examples.

### 25.1 Graph Node Example

```json
{
  "schema_version": "0.1.0",
  "node_id": "node:demo:module:src/app.py",
  "node_type": "module",
  "label": "src/app.py",
  "qualified_name": "app",
  "repo": {
    "repo_id": "repo:demo",
    "name": "demo",
    "root_ref": null,
    "remote_url_hash": null,
    "default_branch": "main"
  },
  "snapshot": {
    "repo_id": "repo:demo",
    "git_sha": "0123456789abcdef0123456789abcdef01234567",
    "branch": "main",
    "worktree_snapshot_id": null,
    "dirty": false,
    "index_status": "fresh",
    "captured_ts": "2026-05-09T00:00:00Z"
  },
  "file_path": "src/app.py",
  "span": {
    "file_path": "src/app.py",
    "start_line": 1,
    "start_col": 1,
    "end_line": 120,
    "end_col": null,
    "byte_start": null,
    "byte_end": null,
    "encoding": "utf-8"
  },
  "provenance": {
    "source_tool": "tree-sitter",
    "source_version": "unknown",
    "source_run_id": null,
    "source_event_id": null,
    "repo": {
      "repo_id": "repo:demo",
      "name": "demo",
      "root_ref": null,
      "remote_url_hash": null,
      "default_branch": "main"
    },
    "snapshot": {
      "repo_id": "repo:demo",
      "git_sha": "0123456789abcdef0123456789abcdef01234567",
      "branch": "main",
      "worktree_snapshot_id": null,
      "dirty": false,
      "index_status": "fresh",
      "captured_ts": "2026-05-09T00:00:00Z"
    },
    "file": "src/app.py",
    "span": null,
    "derivation": "parser",
    "confidence": 1.0,
    "evidence_strength": "hard_static",
    "created_ts": "2026-05-09T00:00:00Z",
    "attributes": {}
  },
  "properties": {
    "language": "python"
  },
  "created_ts": "2026-05-09T00:00:00Z"
}
```

### 25.2 Run Event Example

```json
{
  "schema_family": "run-record",
  "schema_version": "0.1.0",
  "event_id": "event:run:demo:1",
  "run_id": "run:demo",
  "seq": 1,
  "ts": "2026-05-09T00:00:00Z",
  "type": "session_start",
  "actor": "system",
  "stage": "start",
  "input_ref": null,
  "output_ref": null,
  "policy_action": "not_applicable",
  "token_count": null,
  "wall_ms": null,
  "artefact_ids": [],
  "redaction_status": "not_required",
  "payload": {
    "message": "run started"
  }
}
```

---

## 26. Test Plan

### 26.1 Unit Tests

Required unit tests:

- All enums accept only declared values in strict mode.
- Base ID fields reject empty strings.
- Timestamps validate ordering where applicable.
- Source spans reject invalid line ranges.
- Confidence rejects values outside 0.0 to 1.0.
- Provenance rejects missing `source_tool`, `repo`, `snapshot`, `derivation`, or invalid evidence strength.
- LLM-derived provenance cannot claim hard static or hard dynamic evidence.
- Snapshot references represent clean, dirty, stale, partial, mixed, and unknown states.
- Artifact refs require redaction status.

### 26.2 Graph Tests

Required graph tests:

- Valid graph document round-trips through JSON.
- Invalid node type fails.
- Invalid edge type fails.
- Edge with missing endpoint fails complete-document validation.
- Edge with invalid endpoint pairing fails when covered by the endpoint matrix.
- Graph fact without provenance fails.
- Graph fact without repo/snapshot fails.
- Mixed-snapshot graph is detectable.
- LLM-derived edge stays soft evidence.

### 26.3 Evidence And Verdict Tests

Required tests:

- Evidence bundle separates supporting, contradicting, neutral, missing, and stale evidence.
- Positive verdict with only soft LLM evidence fails validation.
- `unknown` verdict with uncertainty reasons passes.
- `unknown` verdict without uncertainty reasons fails or warns according to strictness.
- Calibrated model evidence without calibration metadata fails.
- Hard static contradiction can be represented separately from final aggregation.
- `process-noncompliant`, `trace-incomplete`, and `budget-exhausted` verdicts serialize correctly.

### 26.4 Run Record Tests

Required tests:

- Run record round-trips through JSON.
- Run event sequence validation passes for monotonic sequence.
- Duplicate event sequence fails.
- Event with mismatched `run_id` fails.
- Missing redaction status fails.
- Completed run without `end_ts` fails or warns according to status policy.
- Run without harness condition is marked incomplete for workflow/release evidence.
- Denied policy action can be represented.
- Budget hard stop can be represented.

### 26.5 Operational And Governance Tests

Required tests:

- Tool permission model represents read, search, edit, execute, review, and commit modes.
- Policy decision represents allow, deny, approval required, block, checkpoint, and force unknown.
- Manifest precedence record can represent relaxed drift.
- Hard constraints HC1-HC6 serialize and validate.
- Drift findings classify missing, stale, relaxed, out-of-stage, and clean.
- Relaxed drift can be marked release-blocking.

### 26.6 Readiness Tests

Required tests:

- Axis score outside range fails.
- Total score outside 0 to 25 fails.
- Stage threshold checks represent pass/fail for S0 through S3.
- No-regression result can represent accepted waiver and incident-linked regression.

### 26.7 Incident And Promotion Tests

Required tests:

- Incident without source run or event fails.
- Closed incident without reviewer metadata fails.
- Promotion candidate without source run/event fails.
- Promotion candidate without owner, expiry/review date, or rollback path fails.
- Unreviewed promotion candidate remains non-durable.

### 26.8 JSON Schema Export Tests

Required tests:

- Exported JSON Schema files exist.
- Exported JSON Schema files include `schema_version`.
- Valid fixtures validate against exported schemas.
- Invalid fixtures fail against exported schemas.
- Schema exports are stable under repeated generation.
- Contract-affecting schema changes update regression snapshots deliberately.

---

## 27. Work Packages

### P1.1 Schema Conventions And Base Module

Build:

- Schema version constants.
- Base ID types.
- Timestamp helpers.
- Strict model base.
- JSON value type aliases.
- Canonical serialization helpers.

Deliverables:

- `base.py`
- Tests for IDs, timestamps, strict models, and canonical JSON.

Acceptance:

- Base models reject malformed core primitives.
- Canonical JSON is deterministic.

### P1.2 Provenance, Snapshot, Span, And Artefact Models

Build:

- `RepoRef`
- `SnapshotRef`
- `SourceSpan`
- `ArtifactRef`
- `Provenance`
- Redaction status enum.
- Evidence strength enum.
- Derivation enum.

Deliverables:

- `provenance.py`
- Tests for provenance completeness and snapshot states.

Acceptance:

- Missing provenance fails.
- Dirty, stale, mixed, and clean snapshots are representable.
- LLM-derived hard evidence is rejected.

### P1.3 Graph Schema And Python Models

Build:

- Graph node enum.
- Graph edge enum.
- `GraphNode`
- `GraphEdge`
- `GraphDocument`
- `GraphDiagnostic`
- Endpoint compatibility validator.

Deliverables:

- `graph.py`
- `schemas/graph.schema.json`
- Graph fixtures.

Acceptance:

- Graph documents round-trip through JSON.
- Invalid edges and missing provenance fail.
- Mixed snapshots are detectable.

### P1.4 Repository, File, Symbol, Interface Helpers

Build:

- Typed helper models for repository, file, symbol, and interface records.
- Capability and diagnostic metadata.

Deliverables:

- Helper classes in `graph.py` or separate module if cleaner.
- Tests for repo-relative paths, generated flags, symbol location, and interface confidence.

Acceptance:

- Later indexing phases have clear target payloads for repository, file, symbol, and interface facts.

### P1.5 SARIF Reference And Contract Artefact Models

Build:

- `SarifRunRef`
- `SarifAlertRef`
- `ContractArtifact`
- Compile and run status enums.

Deliverables:

- `sarif.py`
- `contracts.py`
- Fixtures for bound and unbound SARIF alerts.

Acceptance:

- SARIF references preserve analyser, rule, predicate, severity, locations, and provenance.
- Contract artefacts cannot become hard evidence without compile/run status.

### P1.6 Patch, Risk, Evidence, And Verdict Models

Build:

- `PatchRecord`
- `RiskFinding`
- `EvidenceBundle`
- `EvidenceItem`
- `MissingEvidence`
- `StaleEvidence`
- `Verdict`
- `ReasoningStep`
- `Uncertainty`
- `CalibrationRef`

Deliverables:

- `patches.py`
- `evidence.py`
- `verdicts.py`
- Tests for positive, negative, and unknown verdict paths.

Acceptance:

- Positive verdicts cannot be supported only by soft LLM evidence.
- `unknown` verdicts are easy to create and validate with uncertainty reasons.

### P1.7 Run Record And Session Trace Models

Build:

- `RunRecord`
- `RunEvent`
- `SessionTrace`
- Run status enum.
- Event type enum.
- Actor enum.
- Sequence validator.

Deliverables:

- `run_records.py`
- `schemas/run-record.schema.json`
- Valid and invalid run fixtures.

Acceptance:

- Append-only event semantics are enforceable by validation helpers.
- Events are sequence-numbered and redaction-aware.
- Run records can attach harness condition, final verdict, incident IDs, and artefacts.

### P1.8 Operational Payload Models

Build:

- `ToolCallEvent`
- `ApprovalEvent`
- `BudgetEvent`
- `CompactionEvent`
- `MonitorAlert`
- `VerificationEvent`
- `MaintainabilityOracleResult`
- `PromptManifestRegressionResult`

Deliverables:

- `operations.py`
- Tests for denied tools, hard budget stops, compaction loss, monitor alerts, and skipped gates.

Acceptance:

- Every event family required by Phase 4A can be represented before Phase 4A exists.

### P1.9 Governance And Harness Condition Models

Build:

- `ToolPermission`
- `PolicyDecision`
- `ManifestPrecedenceRecord`
- `HardConstraint`
- `HarnessCondition`
- Runtime, model, sandbox, retry, context, verification, and redaction submodels.

Deliverables:

- `governance.py`
- `harness.py`
- `schemas/harness-condition.schema.json`
- `schemas/governance.schema.json`

Acceptance:

- HC1-HC6 are representable.
- Harness Condition Sheets include runtime/model, manifests, tools, permissions, sandbox, context, verification, telemetry, retry, and redaction policy.

### P1.10 Readiness, Drift, Incident, Promotion, Memory, And Supply Chain

Build:

- `HarnessStageAssessment`
- `DriftFinding`
- `AIReadinessReport`
- `ReadinessAxisHistory`
- `Incident`
- `PromotionCandidate`
- `TrajectoryRef`
- `RetentionPolicy`
- `SupplyChainRecord`

Deliverables:

- `readiness.py`
- `incidents.py`
- `memory.py`
- `supply_chain.py`
- `schemas/readiness.schema.json`
- `schemas/incident.schema.json`

Acceptance:

- Readiness scoring and drift classification are schema-backed.
- Incidents and promotions retain source run/event links.
- Supply-chain components can be versioned and referenced by Harness Condition Sheets.

### P1.11 JSON Schema Export And Regression Harness

Build:

- Schema export command or helper.
- Snapshot tests for exported schemas.
- Fixture validation helper.
- Compatibility check helper.

Deliverables:

- `json_schema.py`
- `validation.py`
- JSON Schema export tests.

Acceptance:

- JSON Schema exports are deterministic.
- Valid fixtures pass exported schemas.
- Invalid fixtures fail exported schemas.
- Schema changes are deliberate and reviewable.

---

## 28. Suggested Implementation Order

Recommended order:

1. Base primitives.
2. Provenance and snapshot model.
3. Enums.
4. Graph node/edge/document models.
5. Evidence bundle and verdict model.
6. Run record and run event model.
7. Operational payloads.
8. Harness condition and governance models.
9. Readiness, drift, incident, promotion, memory reference, and supply-chain models.
10. JSON Schema export.
11. Fixtures and regression tests.
12. Documentation updates.

Reasoning:

- Provenance and snapshots are needed by nearly every other model.
- Graph and evidence models should land before operational models that reference graph artefacts.
- Run records should land before incidents, promotions, and readiness reports because those models link back to run evidence.
- JSON Schema exports should happen after model families stabilize enough for snapshot tests.

---

## 29. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 1 |
|---|---|
| Phase 2 - Local graph store and registry | Graph nodes/edges, repo refs, snapshots, run records, operational events, incidents, readiness reports |
| Phase 3 - Repository indexing MVP | File, symbol, module, import, test, build evidence, provenance, graph diagnostics |
| Phase 4 - MCP server core | `graph.schema.json`, `run-record.schema.json`, graph slices, task/run event links, permission metadata |
| Phase 4A - Operational runtime plane | Run records, events, policy decisions, budgets, monitors, harness condition, drift, readiness, incidents, promotions |
| Phase 5 - Language backends | Common graph node/edge/provenance schema for all parser and LSP adapters |
| Phase 6 - SARIF layer | SARIF run and alert refs, `warned_by` edges, SARIF delta refs, evidence bundles |
| Phase 7 - Interface plugins | Interface records and interface graph edges |
| Phase 8 - Repo-QA | Evidence bundles, graph paths, verdict uncertainty, confidence, provenance |
| Phase 9 - Fault localisation | Ranked evidence items, graph slices, memory hints, uncertainty |
| Phase 10 - Evaluation | Harness Condition Sheets, eval run nodes, RDS feature references, reproducible report artefacts |
| Phase 11 - Patch review | Patch records, risk findings, SARIF/test deltas, maintainability oracle results, verdicts |
| Phase 12 - SAST repair | SARIF refs, contract artefacts, patch records, SARIF delta and verification events |
| Phase 13 - Bug-resolve | Run records, DryRUN artefact refs, gate events, patch-risk verdicts, blast-radius evidence |
| Phase 14 - Implementation-check | Clause, contract, predicate, verdict, calibration, harness-policy evidence |
| Phase 15 - Blast radius | Changed graph nodes, interface records, impact evidence bundles |
| Phase 16 - Dynamic traces | Runtime trace nodes, observed-in edges, trace artefact refs, redaction and compaction records |
| Phase 17 - Memory | Trajectory refs, promotion candidates, retention policy, schema-grounded memory fields |
| Phase 18 - Release gates | Calibration refs, Harness Condition Sheets, readiness scores, operational metrics, incidents |
| Phase 19 - Distribution | Schema stability, diagnostics, privacy/export/delete metadata, replayable operational records |

---

## 30. Exit Criteria Mapping

Source Phase 1 exit criterion:

- All schema objects round-trip through JSON.

Concrete Phase 1 acceptance:

- Every model family has at least one valid JSON fixture.
- Fixtures parse into Python models and serialize back to canonical JSON.
- Exported JSON Schema validates the same fixtures.

Source Phase 1 exit criterion:

- Invalid graph edges and missing provenance fail validation.

Concrete Phase 1 acceptance:

- Invalid endpoint pairing test fails.
- Missing provenance node test fails.
- Missing provenance edge test fails.
- Missing repo/snapshot on code-related fact fails.

Source Phase 1 exit criterion:

- Every graph fact can carry `repo`, `git_sha`, optional `worktree_snapshot_id`, `file`, `span`, `confidence`, and `derivation`.

Concrete Phase 1 acceptance:

- `GraphNode` and `GraphEdge` include repo, snapshot, confidence, derivation through provenance.
- Dirty worktree fixture includes `worktree_snapshot_id`.
- Span fixture includes file and line range.

Source Phase 1 exit criterion:

- Every long-running task and workflow can attach trace events, permission mode, context budget, verification results, and Harness Condition Sheet metadata.

Concrete Phase 1 acceptance:

- `RunRecord`, `RunEvent`, `ContextBudget`, `VerificationEvent`, `ToolPermission`, and `HarnessCondition` are implemented.
- A valid fixture links a run, harness condition, tool event, budget event, verification event, and final verdict.

Source Phase 1 exit criterion:

- Every long-running task and workflow can attach a run record with stage/tool/context/gate/monitor/review events.

Concrete Phase 1 acceptance:

- Event types cover stage, tool, context, gate, monitor, review, incident, and final verdict events.
- Sequence validation exists.

Source Phase 1 exit criterion:

- Operational events are append-only, sequence-numbered, and redaction-aware.

Concrete Phase 1 acceptance:

- Sequence validation catches duplicates and gaps where configured.
- Every event has `redaction_status`.
- Complete-run validation fails mismatched run IDs.

Source Phase 1 exit criterion:

- Incidents and promotion candidates reference source run/event IDs.

Concrete Phase 1 acceptance:

- Incident fixtures without source links fail.
- Promotion fixtures without source links fail.

Source Phase 1 exit criterion:

- Schema changes that affect manifests, tool descriptions, or workflow gates have regression tests.

Concrete Phase 1 acceptance:

- Exported schemas are snapshot-tested.
- Governance, harness, and verification schema fixtures are included in regression tests.

---

## 31. Definition Of Done

Phase 1 is done when:

- The checked-in schema files exist and are deterministic.
- Python models exist for every Phase 1 model family.
- The graph schema includes the complete required node and edge enums.
- The run-record schema includes the complete required run and event fields.
- Provenance, snapshot, confidence, derivation, evidence strength, and redaction are mandatory where required.
- Validation rejects missing provenance.
- Validation rejects invalid graph edges.
- Validation can detect stale or mixed snapshots.
- Positive verdicts cannot be backed only by soft LLM evidence.
- Operational events are append-only, sequence-numbered, and redaction-aware.
- Harness Condition Sheets are modelled.
- Policy, permission, budget, monitor, verification, maintainability, readiness, drift, incident, promotion, memory reference, and supply-chain records are modelled.
- Valid and invalid fixtures exist.
- The local verify path runs schema tests.
- The Phase 1 document and schema README explain how later phases must use these contracts.

---

## 32. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Schema becomes too broad and blocks implementation | Phase 1 takes too long and downstream code avoids the schema | Keep stable required fields strict, put future backend-specific data in controlled `properties` or `attributes` |
| Schema becomes too loose | Later workflows can make confident claims without evidence | Require provenance, snapshot, evidence strength, redaction status, and validation helpers |
| LLM evidence is modelled like hard evidence | Unsafe auto-pass behavior later | Separate `confidence` from `evidence_strength`; forbid LLM-derived hard evidence |
| Operational records are treated as logs only | Runs cannot be replayed or reviewed | Model run events as typed, append-only evidence |
| Readiness and governance are deferred | Later release gates lack comparable data | Include harness, readiness, drift, policy, and supply-chain models in Phase 1 |
| JSON Schema exports drift from Python models | MCP clients and external tools validate the wrong contract | Export JSON Schema from Python source of truth and snapshot-test exports |
| Absolute paths or sensitive data leak through schema examples | Privacy and portability issues | Use repo-relative paths and redaction/hash fields by default |

---

## 33. Phase 1 Completion Report Template

When Phase 1 implementation is complete, report:

```text
Phase 1 completion report

Implemented:
- Schema files:
- Python model modules:
- Validation helpers:
- Fixture count:
- Test files:

Verification:
- Unit tests:
- JSON Schema export tests:
- Invalid fixture tests:
- Local verify command:

Exit criteria:
- JSON round trip:
- Invalid graph edges fail:
- Missing provenance fails:
- Graph facts carry repo/snapshot/span/confidence/derivation:
- Run records attach events, budgets, verification, harness condition:
- Operational events append-only and redaction-aware:
- Incidents and promotions link to source run/events:
- Schema regression tests:

Known limitations:
-

Follow-up for Phase 2:
-
```

---

## 34. Minimal First Slice Within Phase 1

If Phase 1 needs to be split further, implement this first:

1. Base primitives.
2. Provenance, snapshot, span, and artefact models.
3. Graph node and edge enums.
4. `GraphNode`, `GraphEdge`, and `GraphDocument`.
5. `RunRecord` and `RunEvent`.
6. `EvidenceBundle` and `Verdict`.
7. JSON round-trip tests.
8. Missing-provenance and invalid-edge tests.
9. Initial `graph.schema.json` and `run-record.schema.json` exports.

This minimal slice unblocks Phase 2 storage and Phase 3 indexing while preserving the most important evidence discipline.
