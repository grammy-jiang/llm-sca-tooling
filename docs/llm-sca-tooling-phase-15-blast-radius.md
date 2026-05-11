# LLM-SCA Tooling Phase 15 Implementation Plan: Cross-Language and Cross-Repository Blast Radius

> Date: 2026-05-09
> Repository name: `evidence-sca`
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 15 - Cross-Language and Cross-Repository Blast Radius
> Primary objective: harden the blast-radius stub from Phase 13 into a full standalone service — change-type-specific traversal policies, eight impact groups, cross-language and cross-repo traversal, C/C++ ABI details, generated-stub reporting, ambiguous-link separation, and a human-readable impact report; graduates the `blast-radius` private skill template.

---

## 1. Phase Summary

Phase 15 hardens the blast-radius stub introduced in Phase 13 into a reusable deterministic impact-analysis service. The Phase 13 stub covered only two-hop direct callers and interface boundaries within a single repo. Phase 15 extends this to full cross-language, cross-repository traversal with change-type-specific policies, ABI-sensitive C/C++ details, and generated-file impact notes.

The central rule for this phase is:

```text
Impact analysis is deterministic: confirmed links come from graph edges with
confidence >= analyser; ambiguous links come from graph edges with confidence
< analyser or from candidate-level interface matching.
Ambiguous links are always reported separately — never merged into confirmed
impact.
Generated files and ABI-sensitive changes always produce explicit notes.
Manual edits to generated artefacts are flagged as policy violations unless
the explicit allowlist permits them.
```

Phase 15 should implement:

- Change-set parser (reuses Phase 11 diff parser output).
- Changed graph node detection.
- Traversal policy engine by change type.
- Five change-type traversal policies.
- Eight impact groups.
- Generated-stub reporting.
- C/C++ ABI-relevant signature detection.
- Template instantiation impact.
- Ownership/nullness edge traversal.
- Build-target reachability.
- Ambiguous interface candidate bucket.
- Cross-repo graph overlay traversal.
- Human-readable impact report with evidence citations.
- Hardened `blast-radius` private skill template.

### Architecture Coverage

Phase 15 covers:

- F8 cross-language and cross-repository blast radius.
- Private `blast-radius` skill template (graduated from Phase 13 stub).

No new MCP tools are introduced by Phase 15. The blast-radius result is consumed internally by `run_issue_resolution` (Phase 13) and `run_patch_review` (Phase 11), and later by `run_implementation_check` (Phase 14).

### Inherited Paper Anchors

Use these anchors in Phase 15 issues, ADRs, and blast-radius reports:

- `rig`
- `logiclens`
- `eagle-x`
- `swe-polybench`
- `defects4c`
- `arise`

## Technology Stack

This phase uses the following libraries from `llm-sca-tooling-tech-stack.md`:

| Library/Tool | PyPI package | Version | Role in this phase |
|---|---|---|---|
| Python | — | 3.12+ | Runtime |
| uv | — | latest | Environment and dependency management |
| NetworkX | `networkx` | >=3.3 | **CORE** — multi-hop traversal, cross-repo impact, ego graphs, change-type-specific traversal policies |
| Pydantic v2 | `pydantic` | >=2.0 | `BlastRadiusConfig`, `TraversalPolicy`, `ImpactRecord`, `CrossRepoImpactRecord`, `BlastRadiusReport` schemas; `extra="forbid"` |
| orjson | `orjson` | >=3.10 | Impact report serialisation, all JSON I/O |
| FastMCP + FastAPI | `fastmcp`, `fastapi` | >=2.0, >=0.115 | Internal consumption by `run_issue_resolution` and `run_patch_review`; no new standalone MCP tool in this phase |
| pytest + pytest-asyncio | `pytest`, `pytest-asyncio` | >=8.0, >=0.23 | Blast-radius service tests; `asyncio_mode="auto"` |

- NetworkX is the core library for this phase: all graph traversal (multi-hop callers/callees, cross-repo overlays, ego graphs for impact grouping) is implemented with NetworkX APIs.
- Ambiguous links (graph edge confidence below analyser threshold) are always stored separately from confirmed links in `AmbiguousLinkRecord`; NetworkX traversal must respect this boundary.
- All blast-radius functions consumed by upstream tools are `async def`; CPU-bound NetworkX operations use `loop.run_in_executor`.
- Rich is restricted to the CLI layer; all other modules use `logging`.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 15 depends on:

- Phase 1 schemas:
  - all graph node and edge types
  - `Verdict` model for impact-risk annotations
- Phase 2 stores:
  - graph store with full node and edge set across all registered repos
  - cross-repo graph overlay capability
- Phase 5 language backends:
  - C/C++ call graph with ABI signatures and template instantiations (from libclang/clangd)
  - TypeScript/Python call graphs for cross-language traversal
- Phase 6 SARIF layer:
  - SARIF alert-to-symbol binding for static-analysis reachability impact
- Phase 7 interface plugins:
  - `InterfaceRecord` and `InterfaceOperation` for interface-boundary traversal
  - `GeneratedArtifactRecord` for generated-file impact detection
- Phase 11 patch review:
  - `ChangedSymbolRecord` as the traversal entry point
  - `InterfaceCompatibilityResult` reused for breaking-change annotation
- Phase 13 bug-resolve:
  - `BlastRadiusStub` model replaced by full `BlastRadiusReport`

### Phase Outputs

Phase 15 should produce:

- `BlastRadiusConfig` model.
- `ChangeType` enum.
- `TraversalPolicy` model per change type.
- `ImpactGroup` enum with eight groups.
- `ImpactRecord` model per affected entity.
- `GeneratedStubImpactNote` model.
- `ABIImpactNote` model.
- `CrossRepoImpactRecord` model.
- `AmbiguousLinkRecord` model.
- `BlastRadiusReport` model (replacing `BlastRadiusStub`).
- `BlastRadiusService` class.
- Hardened `blast-radius` private skill template.
- Blast-radius service tests.

### Non-Goals

Do not implement these in Phase 15:

- Dynamic trace capture for runtime blast-radius validation (Phase 16).
- Trajectory memory for blast-radius patterns (Phase 17).
- Automated blast-radius-based test selection (test selection is Phase 10/18 concern).
- Cross-repo patch application.
- Network-based repo discovery.
- Automated change-notification to affected service owners.

---

## 3. Recommended File Layout

Assuming package name `evidence_sca`:

```text
src/evidence_sca/
  blast_radius/
    __init__.py
    models.py
    change_type.py
    traversal_policy.py
    graph_traversal.py
    impact_groups.py
    generated_stub.py
    abi_impact.py
    cross_repo.py
    sarif_reachability.py
    doc_spec_impact.py
    ambiguous_links.py
    report.py
    service.py

  skills/
    blast_radius.md

tests/
  blast_radius/
    fixtures/
      diffs/
        internal_change.diff
        public_api_change.diff
        idl_schema_change.diff
        security_change.diff
        generated_file_change.diff
      graphs/
        cross_lang_graph.json
        cross_repo_overlay.json
    test_change_type.py
    test_traversal_policy.py
    test_graph_traversal.py
    test_impact_groups.py
    test_generated_stub.py
    test_abi_impact.py
    test_cross_repo.py
    test_sarif_reachability.py
    test_ambiguous_links.py
    test_report.py
    test_service.py
    test_blast_radius_template.py
```

---

## 4. Change-Type Classification

### 4.1 `ChangeType` Enum

```text
ChangeType:
  INTERNAL_IMPLEMENTATION: only internal logic changed; public API unchanged
  PUBLIC_API_CHANGE: public function/method/class signature changed
  IDL_SCHEMA_CONTRACT_CHANGE: IDL, protobuf, OpenAPI, or other schema changed
  SECURITY_SENSITIVE_CHANGE: changed code touches auth, crypto, permissions, or known CWE path
  GENERATED_FILE_CHANGE: changed file is a generated artefact (Phase 7 `generated=True`)
  MIXED: multiple change types in one diff
  UNKNOWN: change type could not be classified
```

### 4.2 Change-Type Detector

The change-type detector receives `ChangedSymbolRecord` list from Phase 11 and classifies the change set:

1. Check Phase 7 `GeneratedArtifactRecord` — if any changed file is `generated=True`, add `GENERATED_FILE_CHANGE`.
2. Check if changed symbols are at public API boundaries (public visibility, no leading underscore, exported in `__init__` / module interface) — add `PUBLIC_API_CHANGE`.
3. Check if changed file paths match IDL/proto/OpenAPI patterns — add `IDL_SCHEMA_CONTRACT_CHANGE`.
4. Check if changed symbols are in security-sensitive graph paths (SARIF alerts with `security` or `CWE` class nearby) — add `SECURITY_SENSITIVE_CHANGE`.
5. Otherwise: `INTERNAL_IMPLEMENTATION`.
6. If more than one change type applies: `MIXED` with a list of applicable types.

---

## 5. Traversal Policies by Change Type

### 5.1 `TraversalPolicy` Model

Required fields:

```text
TraversalPolicy
  change_type
  max_hops
  follow_edge_types
  stop_at_interface_boundary
  include_cross_language
  include_cross_repo
  include_generated_files
  include_test_nodes
  include_sarif_reachability
  include_doc_spec_links
  depth_multiplier_security
  confirmed_only
```

### 5.2 Default Policies by Change Type

| Change type | Max hops | Cross-language | Cross-repo | Stop at interface | SARIF reachability |
|---|---|---|---|---|---|
| INTERNAL_IMPLEMENTATION | 3 | No | No | Yes | No |
| PUBLIC_API_CHANGE | 5 | Yes | Yes | No | No |
| IDL_SCHEMA_CONTRACT_CHANGE | 6 | Yes | Yes | No | Yes |
| SECURITY_SENSITIVE_CHANGE | 4 | Yes | Yes | No | Yes |
| GENERATED_FILE_CHANGE | 2 | No | No | Yes | No |
| MIXED | max of applicable | max of applicable | max of applicable | No | Yes |

### 5.3 Policy Rules

Rules:

- `stop_at_interface_boundary: true` means the traversal does not cross language/service boundaries into downstream services for INTERNAL changes. Boundaries are still reported as impacted.
- `include_cross_repo: true` requires cross-repo graph overlays from Phase 2. If not available, report as `is_partial: true`.
- Security-sensitive changes always have `include_sarif_reachability: true`.

---

## 6. Graph Traversal Engine

### 6.1 Traversal Algorithm

The traversal engine performs a breadth-first traversal from the changed symbol nodes, following the policy's allowed edge types:

```text
for each changed symbol node:
  BFS up to max_hops using allowed edges
  collect all reachable nodes
  annotate each reachable node with hop distance and edge path
  separate confirmed (edge.confidence >= analyser) from ambiguous
```

### 6.2 Allowed Edge Types by Group

Edge types by traversal purpose:

- **Callers/callees**: `calls` (reverse for callers, forward for callees).
- **Dataflow**: `dataflow`.
- **Tests**: `tests`.
- **Interface boundaries**: `exposes`, `consumes`, `ffi`, `implements`.
- **Cross-language**: `ffi`, cross-language `calls` edges from Phase 5.
- **SARIF reachability**: `warns_by` (reverse traversal to find symbols that would trigger an alert if the changed code reached them).
- **Docs/specs**: `documents`, `decomposes_to`, `satisfies`, `violates`.
- **Generated files**: `fixed_by`, `changed_by` (from generated artefact records).

### 6.3 Cross-Repo Traversal

Cross-repo traversal uses Phase 2's cross-repo graph overlay:

1. Identify exported symbols of the changed repo.
2. Query the cross-repo overlay for `consumes` edges from other registered repos to those symbols.
3. Traverse inward into each consuming repo for up to the policy's max hops.
4. Mark all cross-repo impact as `CrossRepoImpactRecord`.

If cross-repo overlay is unavailable or incomplete: set `is_partial: true` and log diagnostic.

---

## 7. Eight Impact Groups

### 7.1 `ImpactGroup` Enum

```text
ImpactGroup:
  DIRECT_CALLERS
  DOWNSTREAM_BEHAVIOURS
  TESTS
  INTERFACES
  SERVICES
  REPOSITORIES
  SARIF_REACHABILITY
  LINKED_DOCS_SPECS
```

### 7.2 `ImpactRecord` Model

Required fields:

```text
ImpactRecord
  group
  node_id
  node_type
  path_from_changed_symbol
  hop_distance
  confidence
  confirmed
  edge_types_used
  change_type_relevance
  breaking_change_flag
  notes
```

### 7.3 Impact Group Population

| Group | Source |
|---|---|
| DIRECT_CALLERS | All nodes with `calls` edge pointing to changed symbols |
| DOWNSTREAM_BEHAVIOURS | Callers-of-callers, via `calls` and `dataflow` beyond first hop |
| TESTS | Nodes reachable via `tests` edge from changed symbols |
| INTERFACES | Nodes at `exposes`, `consumes`, `ffi`, `implements` boundaries |
| SERVICES | Nodes beyond a `exposes`/`consumes` boundary (cross-language or cross-process) |
| REPOSITORIES | Nodes in other registered repos reachable via cross-repo overlay |
| SARIF_REACHABILITY | Static-analysis rules that would activate if changed code reaches a tainted path |
| LINKED_DOCS_SPECS | `document`, `design_clause`, `intent_node` nodes linked via `satisfies`, `documents` edges |

---

## 8. Generated-Stub Impact Reporting

### 8.1 Purpose

Generated files are never to be manually edited unless policy explicitly allows. When a diff touches a generated file or when a changed source contract produces downstream generated stubs, Phase 15 must report this explicitly.

### 8.2 `GeneratedStubImpactNote` Model

Required fields:

```text
GeneratedStubImpactNote
  diff_id
  generated_file_path
  generator_source
  source_contract_node_id
  impact_type
  manual_edit_policy_flag
  recommended_action
```

`impact_type` values:

- `source_contract_changed`: the IDL/schema/protobuf that generates this file was changed; regeneration required.
- `generated_file_directly_changed`: the diff touched a generated file directly; policy check required.
- `downstream_consumer_of_generated`: a consumer of the generated file is in the impact group.

`manual_edit_policy_flag: true` means the diff directly modified a generated file. This is flagged unless the workspace allowlist explicitly permits it.

### 8.3 Rules

Rules:

- Every generated file in the impact set must produce a `GeneratedStubImpactNote`.
- If the source contract changed (IDL/proto), identify all generated stubs and add them to the INTERFACES and SARIF_REACHABILITY groups.
- Manual edits to generated files must be flagged even when the edit is functionally correct.

---

## 9. C/C++ ABI Impact Details

### 9.1 Purpose

C/C++ changes can have binary-incompatible ABI impact that goes beyond the call graph. Phase 15 must report this when the Phase 5 libclang/clangd backend is available.

### 9.2 `ABIImpactNote` Model

Required fields:

```text
ABIImpactNote
  symbol_node_id
  symbol_path
  abi_change_type
  affected_template_instantiations
  ownership_edge_changes
  nullness_edge_changes
  build_target_reachability
  confidence
  diagnostics
```

`abi_change_type` values:

- `signature_changed`: function parameters or return type changed in a way that affects the ABI.
- `vtable_affected`: virtual function changed; all derived classes potentially affected.
- `template_instantiation`: a template parameter changed; all instantiations may need rebuilding.
- `ownership_changed`: unique_ptr/shared_ptr ownership semantics changed.
- `nullness_changed`: nullable/non-null annotation changed.
- `no_abi_impact`: change is ABI-neutral (e.g., inline body only).
- `unknown`: libclang/clangd backend not available for this file.

### 9.3 Build-Target Reachability

When libclang/clangd provides build target information:

- Identify all CMake/Make build targets that include the changed translation unit.
- Identify all targets that depend on those targets (transitively).
- Add the dependent targets to the DOWNSTREAM_BEHAVIOURS group.

### 9.4 Fallback

When the C/C++ backend is unavailable: produce `ABIImpactNote` with `abi_change_type: unknown` and a diagnostic. Do not silently skip ABI analysis.

---

## 10. Cross-Language Traversal Details

### 10.1 Cross-Language Edges

Phase 7 interface plugins provide the cross-language evidence:

- `ffi` edges: foreign-function interface calls between Python/C, Python/C++, or Rust/C.
- `exposes`/`consumes` edges: HTTP routes, WebSocket events, IDL interfaces.

Phase 5 provides:

- Language-specific call edges that cross file/module boundaries.

### 10.2 Traversal Rules

Cross-language traversal rules:

- Follow `ffi` edges only when `include_cross_language: true` in the policy.
- Follow `exposes`/`consumes` edges for INTERFACES and SERVICES groups.
- Low-confidence cross-language edges (Phase 7 candidate edges) go to the ambiguous-link bucket.
- Report the interface type for each cross-language boundary: `http_route`, `websocket_event`, `idl_interface`, `grpc_service`.

---

## 11. SARIF Reachability

### 11.1 Purpose

A code change can make existing SARIF rules more or less likely to fire on paths that include the changed code. SARIF reachability maps which static-analysis rules have alert locations that are reachable from the changed symbols.

### 11.2 Algorithm

1. Collect all SARIF alert nodes from Phase 6 that have `warned_by` edges to symbols within the traversal boundary.
2. For each such alert: check if the alert's data-flow path includes any changed symbol.
3. If yes: include in SARIF_REACHABILITY group with `breaking_change_flag: true` if the change removes a guard that previously blocked the data-flow.
4. Report: rule ID, severity, whether the change increased or decreased risk.

---

## 12. Linked Docs and Specs Impact

### 12.1 Purpose

A code change can invalidate design clauses or implementation-check verdicts stored from Phase 14.

### 12.2 Algorithm

1. Find all `design_clause` and `intent_node` graph nodes that have `satisfies` or `violates` edges to changed symbols.
2. Report them in the LINKED_DOCS_SPECS group.
3. Flag clauses with `satisfied` verdicts as potentially stale.
4. Include clause IDs and the last verdict date so the reviewer can decide whether to re-run `run_implementation_check`.

---

## 13. Ambiguous Link Bucket

### 13.1 Purpose

Candidate-level links from Phase 7 (where interface matching is heuristic, not confirmed) must not be mixed with confirmed graph-traversal impact. They go into a separate bucket.

### 13.2 `AmbiguousLinkRecord` Model

Required fields:

```text
AmbiguousLinkRecord
  source_node_id
  target_node_id
  edge_type
  confidence
  match_method
  reason_ambiguous
  recommended_followup
```

`match_method` values:

- `url_pattern_match`: HTTP route matched by URL pattern, not confirmed consumer binding.
- `name_heuristic`: symbol name suggests cross-language link but no confirmed edge.
- `candidate_edge`: Phase 7 emitted a candidate `exposes`/`consumes` edge, not confirmed.
- `cross_repo_unresolved`: target repo not registered or graph not indexed.

---

## 14. `BlastRadiusReport` Model

### 14.1 Required Fields

```text
BlastRadiusReport
  report_id
  diff_id
  run_id
  change_type
  traversal_policy_ref
  impact_groups
  confirmed_impact_count
  ambiguous_impact_count
  generated_stub_notes
  abi_impact_notes
  cross_repo_impact_records
  ambiguous_links
  is_partial
  partial_reason
  sarif_reachability_summary
  linked_docs_summary
  human_readable_summary
  created_ts
```

### 14.2 `is_partial` Flag

`is_partial: true` when:

- Cross-repo traversal was requested but graph overlay is unavailable or incomplete.
- C/C++ backend not available for ABI analysis.
- Any registered repo has a stale index relative to the diff.

---

## 15. `BlastRadiusService`

### 15.1 Interface

```text
BlastRadiusService
  compute(diff_id, config?) -> BlastRadiusReport
  compute_from_changed_symbols(symbol_ids, change_type, config?) -> BlastRadiusReport
```

### 15.2 Phase 13 Integration

Phase 13's `BlastRadiusStub` is replaced by a call to `BlastRadiusService.compute()`. The `BlastRadiusReport` model has a superset of `BlastRadiusStub` fields so Phase 13 `BugResolveReport` can reference either.

### 15.3 Phase 11 Integration

Phase 11's `run_patch_review` should call `BlastRadiusService` after Phase 15 is available. Phase 11 continues to work with the Phase 13 stub until Phase 15 is deployed.

---

## 16. Hardened `blast-radius` Skill Template

### 16.1 Template Upgrade

The Phase 13 `blast-radius` template was a stub covering only direct callers and interface boundaries within a single repo. The Phase 15 template extends it to:

1. Call `BlastRadiusService.compute(change_set)`.
2. Read the `BlastRadiusReport`.
3. Report all eight impact groups with counts and representative examples.
4. Report generated-stub notes with recommended actions.
5. Report ABI impact for C/C++ changes.
6. Report cross-repo impact.
7. Separate confirmed and ambiguous links explicitly.
8. State `is_partial: true` with partial reason if applicable.
9. Flag SARIF reachability changes.
10. Flag stale implementation-check verdicts in LINKED_DOCS_SPECS.

### 16.2 Rules

Rules:

- Template must never merge ambiguous links with confirmed links in the summary.
- Template must include `is_partial` flag when cross-repo or ABI analysis is unavailable.
- Template snapshot must be stable.

---

## 17. Test Plan

### 17.1 Model Tests

Required:

- All Phase 15 models round-trip through JSON.
- `ChangeType` enum exhaustive.
- `ImpactGroup` enum exhaustive.

### 17.2 Traversal Tests

Required:

- Internal change: traversal stops at interface boundary.
- Public API change: cross-language traversal follows `ffi` edge.
- IDL change: generated stubs added to INTERFACES group.
- Security change: SARIF reachability included.
- Generated file change: `manual_edit_policy_flag: true`.

### 17.3 Impact Group Tests

Required:

- Direct callers populated from `calls` edges.
- Tests populated from `tests` edges.
- Interfaces populated from Phase 7 boundary nodes.
- SARIF reachability populated from alert nodes.
- Linked docs populated from clause nodes.

### 17.4 Ambiguous Link Tests

Required:

- Candidate Phase 7 edge → ambiguous bucket, not confirmed.
- Confirmed edge → confirmed impact.
- Cross-repo unresolved → ambiguous bucket with `is_partial: true`.

### 17.5 Report and Template Tests

Required:

- `BlastRadiusReport` assembles for all five fixture diffs.
- `is_partial: true` when C/C++ backend absent.
- Hardened template renders; snapshot stable.
- Template separates confirmed from ambiguous.

---

## 18. Work Packages

### P15.1 Change-Type Classification and Traversal Policy

Build: `ChangeType` enum; change-type detector; `TraversalPolicy` model; five default policies.

Acceptance: Correct change type for each fixture diff.

### P15.2 Graph Traversal Engine

Build: BFS traversal engine; edge-type filtering by policy; confidence-based confirmed/ambiguous split.

Acceptance: Traversal produces correct impact for fixture call graph.

### P15.3 Eight Impact Groups

Build: `ImpactGroup` enum; `ImpactRecord` model; group population for each group type.

Acceptance: All eight groups populated correctly for fixture diffs.

### P15.4 Generated-Stub and ABI Impact

Build: `GeneratedStubImpactNote` model; generator; `ABIImpactNote` model; libclang/clangd integration (or fallback); build-target reachability.

Acceptance: Generated-file note for changed proto stub; ABI note for changed C++ signature.

### P15.5 Cross-Repo and SARIF Reachability

Build: Cross-repo overlay traversal; `CrossRepoImpactRecord` model; SARIF reachability algorithm.

Acceptance: Cross-repo impact detected for fixture; SARIF reachability populated for security change.

### P15.6 Ambiguous Links and Linked Docs

Build: `AmbiguousLinkRecord` model; candidate edge separation; linked docs/specs impact.

Acceptance: Candidate edges in ambiguous bucket; clause nodes in LINKED_DOCS_SPECS group.

### P15.7 `BlastRadiusReport` and `BlastRadiusService`

Build: `BlastRadiusReport` model; report assembler; `BlastRadiusService`; Phase 13 stub replacement.

Acceptance: Full report produced for all fixture diffs; Phase 13 integration works.

### P15.8 Hardened `blast-radius` Template

Build: Upgraded `blast_radius.md`; all eight groups represented; snapshot test.

Acceptance: Template renders; snapshot stable; confirmed/ambiguous separation present.

---

## 19. Suggested Implementation Order

Recommended order:

1. `ChangeType` enum and change-type detector.
2. `TraversalPolicy` model and default policies.
3. BFS traversal engine with edge-type filtering.
4. Confirmed/ambiguous split.
5. Eight impact group population.
6. Generated-stub impact reporter.
7. ABI impact reporter (or fallback stub).
8. Cross-repo traversal (or `is_partial` stub).
9. SARIF reachability.
10. Linked docs/specs impact.
11. Ambiguous link bucket.
12. `BlastRadiusReport` assembler.
13. `BlastRadiusService`.
14. Phase 13 stub replacement.
15. Phase 11 integration hook.
16. Hardened `blast-radius` template.

---

## 20. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 15 |
|---|---|
| Phase 13 (upgrade) | `BlastRadiusReport` replaces `BlastRadiusStub`; same `report_id` interface |
| Phase 11 (upgrade) | `BlastRadiusReport` integrated into `run_patch_review` scope |
| Phase 14 | LINKED_DOCS_SPECS group flags stale implementation-check verdicts |
| Phase 16 | Dynamic trace scope filter can be narrowed to confirmed blast-radius impact |
| Phase 17 | `BlastRadiusReport.impact_groups` as trajectory context for memory |
| Phase 18 | Cross-language drift checks use REPOSITORIES and SERVICES groups |
| Phase 19 | `blast-radius` template graduates to full implementation |

---

## 21. Exit Criteria Mapping

Source Phase 15 exit criterion:

- Given a diff, the tool reports local, test, interface, cross-repo, SAST, and documentation impact.

Concrete acceptance: All six are covered by DIRECT_CALLERS + DOWNSTREAM_BEHAVIOURS, TESTS, INTERFACES + SERVICES, REPOSITORIES, SARIF_REACHABILITY, and LINKED_DOCS_SPECS.

Source Phase 15 exit criterion:

- Ambiguous links are separated from confirmed links.

Concrete acceptance: `AmbiguousLinkRecord` list is separate from `impact_groups` in `BlastRadiusReport`.

Source Phase 15 exit criterion:

- Generated files and ABI-sensitive C/C++ changes receive explicit impact notes.

Concrete acceptance: `GeneratedStubImpactNote` present for generated-file fixture; `ABIImpactNote` present (or `unknown` fallback) for C++ signature-change fixture.

---

## 22. Definition Of Done

Phase 15 is done when:

- Five change-type traversal policies are implemented with correct edge-type filtering.
- All eight impact groups are populated from graph traversal.
- Generated-stub notes flag manual edits to generated artefacts.
- ABI impact notes produced for C/C++ changes (or explicit `unknown` fallback).
- Cross-repo traversal with `is_partial` when overlay is unavailable.
- SARIF reachability included for security-sensitive and IDL changes.
- Ambiguous links always reported separately from confirmed impact.
- `BlastRadiusReport` assembler produces full report for all fixture diffs.
- Phase 13 `BlastRadiusStub` is replaced by `BlastRadiusService.compute()`.
- Hardened `blast-radius` template renders with stable snapshot.

---

## 23. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Confirmed and ambiguous links merged | Reviewer over-trusts blast radius | Enforce structural separation in `BlastRadiusReport`; test with fixture that has both |
| Cross-repo overlay unavailable silently | Cross-repo impact missed | Always produce `CrossRepoImpactRecord` with `is_partial: true`; never silently skip |
| ABI analysis skipped for C++ | ABI-breaking change not flagged | Produce `ABIImpactNote` with `abi_change_type: unknown` when backend absent; never skip |
| Generated-file manual edit not flagged | Policy violation unreported | Detect `generated=True` flag from Phase 7; flag unconditionally |
| Traversal depth too aggressive | Performance degradation on large repos | Max hops are bounded per policy; hub-dampening from Phase 9 applied |
| SARIF reachability produces too many false impacts | Impact report noise | Require data-flow path to include changed symbol; proximity-only match goes to ambiguous |

---

## 24. Phase 15 Completion Report Template

When Phase 15 implementation is complete, report:

```text
Phase 15 completion report

Implemented:
- ChangeType enum and detector:
- TraversalPolicy (5 change types):
- Graph traversal engine:
- 8 impact groups:
- Generated-stub impact reporting:
- ABI impact (C/C++, or fallback):
- Cross-repo traversal (or is_partial):
- SARIF reachability:
- Linked docs/specs impact:
- AmbiguousLinkRecord separation:
- BlastRadiusReport assembler:
- BlastRadiusService (replaces stub):
- Phase 13 stub replacement:
- blast-radius template (hardened):

Exit criteria:
- 8 impact groups including cross-repo, SAST, docs:
- Ambiguous links separated:
- Generated files and ABI notes explicit:

Known limitations:
-
Follow-up for Phase 16:
-
```

---

## 25. Minimal First Slice Within Phase 15

If Phase 15 needs to be split further, implement this first:

1. `ChangeType` enum and detector.
2. `TraversalPolicy` model for INTERNAL and PUBLIC_API types.
3. BFS traversal engine with confirmed/ambiguous split.
4. DIRECT_CALLERS, DOWNSTREAM_BEHAVIOURS, TESTS, and INTERFACES groups.
5. `GeneratedStubImpactNote` model.
6. `AmbiguousLinkRecord` model.
7. `BlastRadiusReport` model (partial).
8. `BlastRadiusService` basic interface.
9. Phase 13 stub replacement.
10. Hardened `blast-radius` template stub upgrade.

This minimal slice unblocks Phase 13 stub replacement and delivers confirmed/ambiguous separation before the full C/C++ ABI and cross-repo traversal are complete.
