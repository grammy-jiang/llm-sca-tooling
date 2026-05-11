# LLM-SCA Tooling Phase 16 Implementation Plan: Dynamic Trace Augmentation

> Date: 2026-05-09
> Repository name: `evidence-sca`
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 16 - Dynamic Trace Augmentation
> Primary objective: add runtime evidence when static evidence is inconclusive — scoped trace capture (`capture_trace` tool), Python adapter (`sys.settrace`/Hunter), JS/TS and C/C++ adapter placeholders, raw trace artefact store, scope filtering, LLM-compressed trace summarisation, state-diff and divergence-point model, and integration back into fault localisation, bug-resolve, patch-review, and implementation-check.

---

## 1. Phase Summary

Phase 16 is the runtime-evidence phase of `evidence-sca`. Phases 1-15 built comprehensive static evidence: graph index, SARIF layer, repo-QA, fault localisation, patch review, SAST repair, bug-resolve, implementation-check, and blast radius. Phase 16 adds dynamic trace capture as fallback evidence for cases where static analysis is inconclusive.

The central rule for this phase is:

```text
Dynamic trace capture is fallback evidence, not default context.
Raw traces are never inserted wholesale into LLM context.
The compression interface is the mandatory LLM boundary: raw trace artefacts
are stored under HC2 path allowlist; LLM context receives only compressed
events, state diffs, branch decisions, and divergence points, each linked back
to raw trace artefact IDs.
Non-reproducing traces are uncertainty, not disproof.
A trace that fails to reproduce the issue does not prove the issue is absent.
```

Phase 16 should implement:

- `TraceRunContract` model: command, timeout, environment snapshot, scope filter, redaction policy.
- Python trace adapter using `sys.settrace` or Hunter-style hooks.
- JS/TS trace adapter placeholder using Node.js inspector / V8 hooks.
- C/C++ trace/probe adapter placeholder using sanitizers, `rr`, `gdb`, or project-specific probes.
- Raw trace artefact store and artefact writer.
- Scope filter engine.
- Trace compression/summarisation interface (LLM boundary).
- State-diff model and divergence-point model.
- `CompressedTrace` model suitable for LLM context.
- Integration hooks for fault localisation (Phase 9), implementation-check (Phase 14), bug-resolve (Phase 13), and patch-review (Phase 11).
- `capture_trace` task-capable MCP tool.

### Architecture Coverage

Phase 16 covers:

- F9 dynamic trace augmentation.
- `capture_trace` tool.
- Integration with F2 (fault localisation), F4 (implementation-check), F5 (bug-resolve), F6 (patch-review).

Tools in this phase:

- `capture_trace`

### Inherited Paper Anchors

Use these anchors in Phase 16 issues, ADRs, and trace reports:

- `trace-prompt`
- `daira`
- `tracerepair`
- `inspectcoder`
- `agent-coevo`

## Technology Stack

This phase uses the following libraries from `llm-sca-tooling-tech-stack.md`:

| Library/Tool | PyPI package | Version | Role in this phase |
|---|---|---|---|
| Python | — | 3.12+ | Runtime; `sys.settrace` used directly by `PyTraceAdapter` |
| uv | — | latest | Environment and dependency management |
| Pydantic v2 | `pydantic` | >=2.0 | `TraceRunContract`, `ScopeFilter`, `RawTraceArtefact`, `StateDiff`, `DivergencePoint`, `CompressedTrace` schemas; `extra="forbid"` |
| orjson | `orjson` | >=3.10 | Raw trace artefact storage, compressed trace payload serialisation, all JSON I/O |
| FastMCP + FastAPI | `fastmcp`, `fastapi` | >=2.0, >=0.115 | `capture_trace` MCP tool handler |
| httpx | `httpx` | >=0.27 | `PolicyAwareHTTPClient` wrapping for HC5 |
| pytest + pytest-asyncio | `pytest`, `pytest-asyncio` | >=8.0, >=0.23 | Trace artefact tests; `asyncio_mode="auto"` |

- Trace capture subprocesses (sanitizer/rr/gdb adapters) use `asyncio.create_subprocess_exec`; `subprocess.run` is forbidden.
- CPU-bound trace compression and state-diff computation use `loop.run_in_executor`.
- All tool handlers and adapter functions are `async def`.
- Rich is restricted to the CLI layer; all other modules use `logging`.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 16 depends on:

- Phase 1 schemas:
  - `RunRecord` and `RunEvent` models
  - `HarnessConditionSheet` model
  - `runtime_trace` graph node type
  - `observed_in` edge type
- Phase 2 stores:
  - artefact registry for raw trace storage
  - graph store for trace-to-symbol binding
- Phase 4 infrastructure:
  - task manager and task persistence
  - HC2 path allowlist for sandbox execution
- Phase 5 language backends:
  - Python AST index for scope-filter resolution
- Phase 9 fault localisation:
  - `LocalisationResult.ranked_candidates` as the scope seed for trace capture
- Phase 10 evaluation harness:
  - `HarnessConditionSheet` attachment per trace run
  - `test_brittleness` RDS axis benefits from perturbation runner integrated with trace
- Phase 11 patch review:
  - `DryRUNMismatch` model accepts trace evidence for mismatch diagnosis
- Phase 13 bug-resolve:
  - Stage 6 optional trace hook in the gate runner
  - `ReproductionTestRecord` with `post_fix_result` supplemented by trace evidence
- Phase 14 implementation-check:
  - Stage 6b `DynamicVerdictRecord` populated by `capture_trace` output

### Phase Outputs

Phase 16 should produce:

- `TraceRunContract` model.
- `ScopeFilter` model.
- `RawTraceArtefact` model.
- `TraceEvent` model.
- `StateDiff` model.
- `DivergencePoint` model.
- `CompressedTrace` model.
- `TraceSummarizerInterface` (LLM boundary).
- `NullTraceSummarizer` (deterministic test double).
- Python trace adapter (`PyTraceAdapter`).
- JS/TS trace adapter placeholder (`JSTraceAdapterPlaceholder`).
- C/C++ trace adapter placeholder (`CppTraceAdapterPlaceholder`).
- `TraceAdapterRegistry`.
- `TraceRunResult` model.
- `capture_trace` task-capable tool handler.
- Phase 9, 11, 13, 14 integration hooks.
- Trace artefact tests.

### Non-Goals

Do not implement these in Phase 16:

- Full JS/TS or C/C++ trace adapters beyond placeholders.
- Real-time streaming trace output to MCP clients.
- Trace-based test generation (Phase 17 may use trace artefacts for trajectory memory, but that is separate).
- Automated trace-to-patch inference without the Phase 13 repair loop.
- Trace data used as durable memory (Phase 17 handles this with its own write-path validation).
- Broad unrestricted trace capture without a scope filter (HC5: deny-by-default network egress; trace capture must be similarly scope-limited).

---

## 3. Recommended File Layout

Assuming package name `evidence_sca`:

```text
src/evidence_sca/
  traces/
    __init__.py
    models.py
    contract.py
    scope_filter.py
    artefact_store.py
    adapters/
      __init__.py
      base.py
      python_adapter.py
      js_adapter.py
      cpp_adapter.py
      registry.py
    compression/
      __init__.py
      interface.py
      null_summarizer.py
      state_diff.py
      divergence.py
    integration/
      __init__.py
      fl_hook.py
      impl_check_hook.py
      bug_resolve_hook.py
      patch_review_hook.py

  mcp_server/
    tools/
      traces.py

tests/
  traces/
    fixtures/
      scripts/
        reproducer_simple.py
        reproducer_exception.py
        no_reproduce.py
      raw_traces/
        simple_trace.jsonl
        exception_trace.jsonl
    test_contract.py
    test_scope_filter.py
    test_artefact_store.py
    test_python_adapter.py
    test_js_placeholder.py
    test_cpp_placeholder.py
    test_null_summarizer.py
    test_state_diff.py
    test_divergence.py
    test_capture_trace_tool.py
    test_fl_hook.py
    test_impl_check_hook.py
    test_bug_resolve_hook.py
    test_patch_review_hook.py
```

---

## 4. Trace Run Contract

### 4.1 `TraceRunContract` Model

Required fields:

```text
TraceRunContract
  contract_id
  command
  args
  timeout_seconds
  environment_snapshot
  working_dir
  scope_filter
  redaction_policy
  max_raw_trace_bytes
  max_compressed_events
  language
  adapter_id
  sandbox_required
```

### 4.2 Rules

Rules:

- `command` must be within the registered repo's path allowlist (HC2). A command that resolves outside the allowlist is rejected before the trace run begins.
- `timeout_seconds` is mandatory and hard-bounded by `WorkflowConfig.wall_clock_budget_seconds`.
- `scope_filter` is mandatory; empty scope filter is rejected (full-repo tracing is not permitted by default).
- `redaction_policy` inherits from the workspace policy; it controls which file paths, variable names, and values are scrubbed from the raw trace artefact.
- `max_raw_trace_bytes` caps the raw trace artefact size; when exceeded, the trace adapter stops and records a truncation diagnostic.

### 4.3 Environment Snapshot

The environment snapshot must include:

- Python version, interpreter path.
- Installed package versions (from lockfile if uv-managed, else `pip freeze`).
- Git SHA of the workspace.
- Sandbox/container descriptor if applicable.
- Any environment variables required for the command (minus secrets, which are redacted).

---

## 5. Scope Filter Engine

### 5.1 Purpose

The scope filter prevents trace explosion by restricting which modules, files, and functions are traced. It is derived from the static suspect list.

### 5.2 `ScopeFilter` Model

Required fields:

```text
ScopeFilter
  include_modules
  include_files
  include_functions
  exclude_patterns
  max_call_depth
  trace_stdlib
  trace_third_party
  derived_from_fl_result
  derived_from_changed_symbols
```

### 5.3 Scope Derivation

The scope is derived from upstream static evidence:

1. **From fault localisation**: include the top-3 file suspects and their two-hop neighbours.
2. **From changed symbols**: include files and modules containing changed symbols.
3. **Always exclude**: `stdlib` modules (unless `trace_stdlib: true` is explicitly set) and third-party packages (unless `trace_third_party: true`).
4. **Always exclude**: test fixtures, CI scripts, and documentation build scripts.

Rules:

- If scope is empty after derivation: reject the trace run with `scope_empty` diagnostic.
- `max_call_depth` defaults to 10; beyond this depth, events are aggregated and not individually recorded.

---

## 6. Python Trace Adapter

### 6.1 Architecture

The `PyTraceAdapter` uses `sys.settrace` to install a per-thread trace function that records:

- Function entry (`call`): module, function name, args (redacted per policy), source file, line number.
- Function exit (`return`): return value type and hash (not full value).
- Exception (`exception`): exception type, message (redacted), source file, line.
- Line-level events: suppressed by default; enabled only when `trace_lines: true` and within `max_raw_trace_bytes`.

### 6.2 `TraceEvent` Model

Required fields:

```text
TraceEvent
  event_id
  event_type
  module
  function
  file_path
  line_number
  depth
  arg_type_hints
  return_type_hash
  exception_type
  exception_message_redacted
  ts_ns
  redaction_applied
```

`event_type` values:

- `call`
- `return`
- `exception`
- `line` (suppressed by default)

### 6.3 Hunter-Style Tracing Alternative

When the `hunter` package is available, it may be used as an alternative to `sys.settrace`. The adapter interface is the same regardless of the underlying mechanism. Preference: `sys.settrace` for maximum portability; `hunter` for richer filtering in development.

### 6.4 `RawTraceArtefact` Model

Required fields:

```text
RawTraceArtefact
  artefact_id
  trace_run_id
  language
  adapter_version
  events_jsonl_path
  event_count
  truncated
  truncation_reason
  size_bytes
  git_sha
  environment_snapshot_hash
  redaction_policy_hash
  created_ts
```

### 6.5 Rules

Rules:

- Raw trace JSONL is stored in the artefact store, not in the graph or run record.
- Raw trace content is never inserted into LLM context.
- Artefact path must be within the HC2 workspace allowlist.
- Truncated traces record the truncation reason and the last event before truncation.

---

## 7. Language Adapter Placeholders

### 7.1 JS/TS Trace Adapter Placeholder

`JSTraceAdapterPlaceholder` accepts a `TraceRunContract` with `language: "javascript"` or `language: "typescript"` and:

- Returns a `TraceRunResult` with `status: not_implemented`.
- Records a diagnostic: `js_trace_adapter_not_available`.
- Does not attempt to execute the command.

Future implementation: Node.js `--inspect` protocol / V8 inspector, capturing function-entry/exit events for scoped modules.

### 7.2 C/C++ Trace Adapter Placeholder

`CppTraceAdapterPlaceholder` accepts a `TraceRunContract` with `language: "cpp"` or `language: "c"` and:

- Returns a `TraceRunResult` with `status: not_implemented`.
- Records a diagnostic: `cpp_trace_adapter_not_available`.
- Notes the planned mechanisms: sanitizers (AddressSanitizer, UBSan), `rr` (Mozilla record-and-replay), `gdb` breakpoint-based trace, or project-specific probe hooks.
- Does not attempt to execute the command.

### 7.3 `TraceAdapterRegistry`

The registry maps language string to adapter class:

```text
TraceAdapterRegistry
  register(language, adapter_class)
  get(language) -> TraceAdapterBase
  available_languages() -> list[str]
```

---

## 8. Trace Compression and Summarisation

### 8.1 Purpose

The compression interface reduces a raw `RawTraceArtefact` (potentially millions of events) to a bounded `CompressedTrace` that fits within LLM context. The compression step is the **mandatory LLM boundary** for trace data.

### 8.2 `TraceSummarizerInterface` Abstract Interface

```text
TraceSummarizerInterface
  summarize(raw_artefact, scope_filter, budget_tokens) -> CompressedTrace
  model_id
  version
```

### 8.3 `CompressedTrace` Model

Required fields:

```text
CompressedTrace
  trace_run_id
  raw_artefact_id
  executed_path_summary
  relevant_events
  state_diffs
  divergence_points
  exception_events
  compressed_token_estimate
  compression_ratio
  scope_coverage
  uncertainty_notes
  summarizer_model
  confidence
```

`relevant_events` is a bounded list of `TraceEvent` objects selected by the summarizer for their divergence or exception significance — maximum 50 events by default.

### 8.4 `NullTraceSummarizer`

For testing without LLM calls:

- Returns a deterministic `CompressedTrace` with pre-canned `relevant_events`.
- `confidence: unknown`.
- `summarizer_model: null`.
- All fields populated; no LLM call made.

---

## 9. State Diff and Divergence-Point Model

### 9.1 `StateDiff` Model

Required fields:

```text
StateDiff
  trace_run_id
  function_path
  parameter_before
  parameter_after
  return_before
  return_after
  side_effect_detected
  diff_type
  confidence
```

`diff_type` values:

- `value_change`: same function invoked with different parameter values.
- `exception_vs_return`: function raised exception in one trace but returned normally in another.
- `path_divergence`: execution took a different branch.
- `new_call`: function was called in one trace but not the other.
- `missing_call`: function was not called in one trace but was in the other.

### 9.2 `DivergencePoint` Model

Required fields:

```text
DivergencePoint
  trace_run_id
  function_path
  file_path
  line_number
  divergence_type
  pre_fix_event_ref
  post_fix_event_ref
  graph_node_id
  confidence
  notes
```

`divergence_type` values:

- `branch_taken_vs_not_taken`
- `exception_raised_vs_not`
- `return_value_type_mismatch`
- `call_order_change`
- `missing_call`
- `new_call`

### 9.3 Two-Trace Comparison

When `capture_trace` is invoked for both pre-fix and post-fix versions:

- Compare the two raw artefacts using event sequences.
- Identify divergence points by aligning function-call stacks.
- Produce `StateDiff` entries for each differing invocation.
- Bind divergence points to graph nodes where possible (via file path and symbol resolution).

---

## 10. `TraceRunResult` Model

### 10.1 Required Fields

```text
TraceRunResult
  trace_run_id
  contract_id
  language
  adapter_id
  status
  raw_artefact_ref
  compressed_trace_ref
  state_diffs
  divergence_points
  non_reproducing
  harness_condition_id
  run_id
  wall_ms
  diagnostics
```

`status` values:

- `completed`: trace ran successfully and produced artefact.
- `timeout`: trace exceeded `timeout_seconds`.
- `scope_empty`: scope filter produced no traceable symbols.
- `out_of_scope`: command resolved outside path allowlist.
- `not_implemented`: adapter placeholder returned not-implemented.
- `truncated`: raw artefact hit `max_raw_trace_bytes` limit.
- `not_reproducing`: the command ran but did not trigger the expected failure.
- `failed`: trace adapter raised an unhandled error.

### 10.2 Non-Reproducing Semantics

Rules:

- `non_reproducing: true` means the reproduction command ran without triggering the expected exception, assertion, or failure behaviour.
- A non-reproducing trace is uncertainty evidence, not disproof.
- `non_reproducing` must never produce a `satisfied` verdict for a dynamic clause check.
- `non_reproducing` is reported as `DynamicVerdictRecord.verdict: unknown`.

---

## 11. `capture_trace` Tool

### 11.1 Purpose

Execute a scoped trace run and return a compressed trace suitable for LLM context, with the raw artefact stored separately.

### 11.2 Input

```text
script
args?
scope_filter?
suspects?
timeout_seconds?
language?
pre_fix?
post_fix?
null_mode?
task?
```

`suspects` accepts a list of file paths or symbol paths from Phase 9 fault localisation to auto-derive the scope filter.

`pre_fix` and `post_fix` are boolean flags for two-trace comparison (before and after a candidate patch).

### 11.3 Output

- `TaskCreateResult` for the trace task.
- On completion: `TraceRunResult` with compressed trace and divergence points.

### 11.4 Workflow

1. Create `TraceRunContract` from inputs.
2. Validate command against HC2 path allowlist.
3. Derive scope filter from `suspects` or explicit `scope_filter`.
4. Resolve language adapter.
5. Create run record and task.
6. Execute adapter (or placeholder).
7. Store `RawTraceArtefact`.
8. Run trace compression/summarization (`NullTraceSummarizer` in null mode).
9. If `post_fix` and prior pre-fix trace is available: compute state diffs and divergence points.
10. Bind divergence points to graph nodes.
11. Attach `HarnessConditionSheet`.
12. Return `TraceRunResult`.

### 11.5 Permissions

- Required mode: execute (trace capture requires process execution).
- Path scope: registered repo roots and sandbox workspace.
- Network: none.
- Side effect: writes raw trace artefact and operational records.
- Approval: execute mode requires approval in policy-enforced mode.

### 11.6 Tests

Required tests:

- Null-mode run with `reproducer_simple.py`: completes with `CompressedTrace`.
- Scope-empty contract rejected with `scope_empty` diagnostic.
- Out-of-scope command rejected before execution.
- Non-reproducing script produces `non_reproducing: true`, not `not_implemented`.
- JS/TS placeholder returns `not_implemented` gracefully.
- `HarnessConditionSheet` attached to every result.
- Raw artefact stored; not in run record directly.

---

## 12. Integration Hooks

### 12.1 Fault Localisation Hook (Phase 9)

The FL hook allows a caller to optionally augment fault localisation with trace evidence:

- After `get_relevant_files` returns, if the caller provides a reproduction script:
  - Call `capture_trace(script, suspects=ranked_candidates[:3])`.
  - If divergence points bind to graph nodes, add those nodes to the suspect ranking with `confidence: trace`.
  - Divergence points do not replace static suspects; they are additional evidence.

### 12.2 Implementation-Check Hook (Phase 14 Stage 6b)

The implementation-check Stage 6b hook calls `capture_trace` when:

- A clause has `checkability: dynamic` or `checkability: hybrid`.
- A reproduction script is available.
- Phase 16 is deployed.

Returns `DynamicVerdictRecord` with `available: true` and the compressed trace.

### 12.3 Bug-Resolve Hook (Phase 13 Gate Runner)

The bug-resolve gate runner calls `capture_trace` (pre-fix mode) when:

- Static gates pass but certificate conclusion is `partially_supported` or `unsupported`.
- A reproduction script is available.
- `WorkflowConfig` allows dynamic trace.

If post-fix trace also requested: compute state diffs, compare divergence points before/after patch.

### 12.4 Patch-Review Hook (Phase 11)

The patch-review `DryRUNMismatch` model gains an optional `trace_divergence_ref` field pointing to a `DivergencePoint` that explains the mismatch.

---

## 13. Redaction Policy

### 13.1 Trace Redaction Rules

Rules enforced during trace capture and artefact storage:

- Variable values in `call` events are not stored verbatim; only type name and a salted hash are stored.
- Exception messages are stored as `exception_message_redacted: true` unless the redaction policy explicitly allows exception messages for the current data class.
- File paths in the trace are stored as repo-relative paths only.
- Arguments containing secrets (matched by the HC1 secret scanner patterns) are replaced with `[REDACTED]`.
- The redaction policy is hashed and stored in `RawTraceArtefact.redaction_policy_hash` for audit.

### 13.2 Compression Redaction

The trace summarizer must apply the same redaction policy to `CompressedTrace.relevant_events`. Compressed events must not include unredacted values that were redacted in the raw artefact.

---

## 14. Test Plan

### 14.1 Model Tests

Required:

- All Phase 16 models round-trip through JSON.
- `TraceRunResult.status` enum exhaustive.
- `DivergencePoint.divergence_type` enum exhaustive.

### 14.2 Adapter Tests

Required:

- `PyTraceAdapter` captures call/return/exception events for fixture script.
- Scope filter excludes stdlib events.
- `max_raw_trace_bytes` truncation fires correctly.
- JS placeholder returns `not_implemented`.
- C/C++ placeholder returns `not_implemented`.

### 14.3 Compression Tests

Required:

- `NullTraceSummarizer` produces deterministic `CompressedTrace`.
- `relevant_events` bounded to max 50.
- Raw artefact not present in `CompressedTrace` payload.

### 14.4 State Diff and Divergence Tests

Required:

- `StateDiff` detects exception vs. return for fixture pair.
- `DivergencePoint` binds to graph node.
- Non-reproducing trace produces `non_reproducing: true`.

### 14.5 Tool Tests

Required:

- Null-mode `capture_trace` task lifecycle.
- Scope-empty rejection.
- Out-of-scope command rejection.
- `HarnessConditionSheet` attached to result.

### 14.6 Integration Hook Tests

Required:

- FL hook adds trace suspects without replacing static suspects.
- Implementation-check Stage 6b produces `DynamicVerdictRecord` with trace ref.
- Bug-resolve gate runner invokes trace hook when configured.
- Patch-review mismatch links divergence point.

---

## 15. Work Packages

### P16.1 Trace Run Contract and Scope Filter

Build: `TraceRunContract`, `ScopeFilter` models; scope derivation from FL suspects; path-allowlist validation.

Acceptance: Contract rejected when out-of-scope; scope derived correctly from suspects.

### P16.2 Python Trace Adapter

Build: `PyTraceAdapter`; `TraceEvent` model; `sys.settrace` integration; size-bounded artefact writer.

Acceptance: Fixture script traced; stdlib excluded; truncation fires.

### P16.3 Adapter Placeholders and Registry

Build: `JSTraceAdapterPlaceholder`; `CppTraceAdapterPlaceholder`; `TraceAdapterRegistry`.

Acceptance: Placeholders return `not_implemented` with diagnostics.

### P16.4 Raw Trace Artefact Store

Build: `RawTraceArtefact` model; JSONL artefact writer; HC2-compliant path management.

Acceptance: Artefact stored and retrievable; path within allowlist.

### P16.5 Trace Compression

Build: `TraceSummarizerInterface`; `CompressedTrace` model; `NullTraceSummarizer`.

Acceptance: Null summarizer produces deterministic output; raw artefact not in compressed payload.

### P16.6 State Diff and Divergence Points

Build: `StateDiff` model; `DivergencePoint` model; two-trace comparison algorithm; graph-node binding.

Acceptance: Divergence detected for pre/post-fix fixture pair.

### P16.7 `capture_trace` Tool

Build: `TraceRunResult` model; full tool orchestration; task-capable handler; `HarnessConditionSheet` attachment.

Acceptance: Null-mode task completes with full result.

### P16.8 Integration Hooks

Build: FL hook; Phase 14 Stage 6b hook; Phase 13 gate runner hook; Phase 11 mismatch field.

Acceptance: Each hook invoked correctly in integration tests.

### P16.9 Redaction

Build: Trace redaction engine; compression redaction pass; redaction policy hash.

Acceptance: Secret-scanner pattern match in args produces `[REDACTED]`; compressed events also redacted.

---

## 16. Suggested Implementation Order

Recommended order:

1. `TraceRunContract` and `ScopeFilter` models.
2. Path-allowlist validation.
3. `PyTraceAdapter` and `TraceEvent` model.
4. `RawTraceArtefact` store.
5. Redaction engine.
6. Adapter placeholders and registry.
7. `NullTraceSummarizer` and `CompressedTrace` model.
8. `StateDiff` and `DivergencePoint` models.
9. Two-trace comparison.
10. `TraceRunResult` model.
11. `capture_trace` task-capable tool.
12. FL integration hook.
13. Phase 14 Stage 6b hook.
14. Phase 13 gate runner hook.
15. Phase 11 mismatch field.

---

## 17. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 16 |
|---|---|
| Phase 13 (upgrade) | Gate runner hook; state diffs for DryRUN mismatch diagnosis |
| Phase 14 (upgrade) | Stage 6b `DynamicVerdictRecord` populated by trace |
| Phase 17 - Memory | `RawTraceArtefact` as a trajectory-linked evidence artefact (not raw memory) |
| Phase 18 - Release gates | Trace replay success rate; `capture_trace` available flag in HarnessConditionSheet |
| Phase 19 - Distribution | `capture_trace` tool |

---

## 18. Exit Criteria Mapping

Source Phase 16 exit criterion:

- `capture_trace(script, scope_filter)` stores raw trace and returns compressed evidence.

Concrete acceptance: Null-mode run stores `RawTraceArtefact` and returns `CompressedTrace` with bounded events.

Source Phase 16 exit criterion:

- Non-reproducing traces are represented as uncertainty rather than hard disproof.

Concrete acceptance: `no_reproduce.py` fixture produces `non_reproducing: true` and `DynamicVerdictRecord.verdict: unknown`.

---

## 19. Definition Of Done

Phase 16 is done when:

- `TraceRunContract` validates scope and path allowlist before execution.
- `PyTraceAdapter` traces `call`, `return`, and `exception` events for fixture scripts.
- Scope filter excludes stdlib and third-party packages by default.
- Raw trace artefact stored within HC2 allowlist; never in run record directly.
- Redaction engine removes secret-matched values before artefact storage.
- `NullTraceSummarizer` produces deterministic `CompressedTrace` for testing.
- Raw trace content never appears in `CompressedTrace` payload.
- State diffs and divergence points detected for pre/post-fix fixture pair.
- `capture_trace` null-mode task completes with typed result.
- JS/TS and C/C++ placeholders return `not_implemented` gracefully.
- Non-reproducing traces produce `non_reproducing: true` and `unknown` dynamic verdict.
- `HarnessConditionSheet` attached to every `TraceRunResult`.
- FL, implementation-check, bug-resolve, and patch-review integration hooks are implemented.

---

## 20. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Raw trace inserted into LLM context | Context budget exhaustion; privacy leak | Enforce `CompressedTrace` as the only trace model passed to LLM; raw artefact path never in model input |
| Scope filter too permissive | Trace explosion and budget hard-stop | Require explicit `scope_filter` or FL-derived scope; reject empty scope |
| Non-reproducing trace interpreted as disproof | False `satisfied` dynamic verdict | Enforce `non_reproducing → verdict: unknown` rule; test with fixture |
| Out-of-scope command executed | HC2 violation; arbitrary code execution | Validate command against path allowlist before adapter invocation; reject before any execution |
| Redaction misses sensitive values | Secrets in raw trace artefact | Apply redaction during event recording, not post-hoc; run HC1 secret scanner on artefact after write |
| Timeout not enforced | Long-running trace blocks workflow | Hard timeout in `TraceRunContract`; adapter SIGKILL after timeout; task monitor fires `wall_clock_budget_hard_stop` |
| Two-trace comparison misaligns | Wrong divergence points | Align by call-stack depth and function path, not by absolute event index |

---

## 21. Phase 16 Completion Report Template

When Phase 16 implementation is complete, report:

```text
Phase 16 completion report

Implemented:
- TraceRunContract and ScopeFilter models:
- Path-allowlist validation:
- PyTraceAdapter (sys.settrace):
- RawTraceArtefact store:
- Redaction engine:
- JS/TS adapter placeholder:
- C/C++ adapter placeholder:
- TraceAdapterRegistry:
- NullTraceSummarizer:
- CompressedTrace model:
- StateDiff and DivergencePoint models:
- Two-trace comparison:
- capture_trace task-capable tool:
- FL integration hook:
- Phase 14 Stage 6b hook:
- Phase 13 gate runner hook:
- Phase 11 mismatch field:

Exit criteria:
- capture_trace stores raw trace and returns compressed evidence:
- Non-reproducing traces are uncertainty, not disproof:

Known limitations:
-
Follow-up for Phase 17:
-
```

---

## 22. Minimal First Slice Within Phase 16

If Phase 16 needs to be split further, implement this first:

1. `TraceRunContract` model.
2. Path-allowlist validator.
3. `ScopeFilter` model and derivation from FL suspects.
4. `PyTraceAdapter` with `sys.settrace`.
5. `RawTraceArtefact` store (JSONL writer).
6. Redaction engine.
7. `NullTraceSummarizer` and `CompressedTrace` model.
8. `TraceRunResult` model.
9. `capture_trace` null-mode task tool.
10. Phase 14 Stage 6b hook stub.

This minimal slice makes `capture_trace` callable from MCP clients in null mode, activates the Phase 14 Stage 6b hook, and establishes the raw-trace/compressed-trace separation before the full state-diff and integration-hook work is complete.
