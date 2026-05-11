# LLM-SCA Tooling Phase 5 Implementation Plan: Language Backend Expansion

> Date: 2026-05-09  
> Repository name: `evidence-sca`  
> Source plan: `llm-sca-tooling-implementation-plan.md`  
> Source architecture: `llm-sca-tooling-architecture.md`  
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 5 - Language Backend Expansion  
> Primary objective: expand deterministic graph coverage from the Phase 3 Python MVP to JavaScript/TypeScript and C/C++ targets, harden the Python backend with a call-graph adapter and LSP integration, introduce a shared LSP abstraction layer, add backend capability reporting, and implement cross-backend fact reconciliation so that every graph edge carries calibrated confidence and a derivation source.

---

## 1. Phase Summary

Phase 3 established the first deterministic index for Python repositories. Phase 4 exposed that index through MCP resources and tools. Phase 5 expands the evidence base across the three language targets the architecture requires before multi-language fault localisation, blast-radius, SARIF alert repair, and end-to-end workflows can be trusted.

The central rule for this phase is:

```text
Language backends are evidence producers, not feature flags.
Every backend must emit typed graph facts, diagnostics, and confidence metadata
that match the Phase 1 schema — or degrade explicitly to partial evidence.
A missing backend must never break an existing index or suppress indexing diagnostics.
```

Phase 5 should implement:

- Python backend hardening: `pyan3` call-graph adapter, Pyright or LSP adapter for type-aware references and diagnostics.
- JavaScript/TypeScript backend: `ts-morph` adapter for symbol/import/call analysis, `madge` adapter for dependency graph, package metadata, and test-runner detection.
- C/C++ backend: `libclang` adapter for AST-level symbols and includes, `clangd` LSP adapter for references and diagnostics, `compile_commands.json` parser, CMake File API integration, and CTest evidence detection.
- Optional Java backend: gated by capability flag, exercisable by Java calibration fixtures when enabled.
- Shared LSP abstraction layer: reusable JSON-RPC client with process lifecycle, capability negotiation, request dispatch, and timeout handling — shared across Pyright, `clangd`, and `typescript-language-server`.
- Backend capability registry: each backend reports what node types, edge types, and confidence levels it can contribute.
- Cross-backend fact reconciliation: compare parser, ctags, and LSP facts and attach evidence strength per edge and node.
- Incremental update hooks for new language backends through the Phase 3 pipeline.

### Architecture Coverage

Phase 5 covers:

- F1 multi-language graph.
- Intra-language indexing backends for Python, JavaScript/TypeScript, and C/C++.
- Optional Java benchmark/customer parity backend.

All backends output to the Phase 1 graph schema. No backend-specific schema extensions are permitted.

### Inherited Paper Anchors

Use these anchors in Phase 5 issues, ADRs, backend design notes, and capability reports:

- `arise`
- `locagent`
- `marscode`
- `rig`
- `swe-polybench`
- `defects4c`
- `predicatefix`

Adjacent anchors useful for LSP and cross-language notes:

- `logiclens`
- `eagle-x`
- `cosil`
- `repo-aware-kg`
- `repograph`
- `codexgraph`

## Technology Stack

Libraries and tools active in Phase 5. All versions are minimum constraints; exact pins are in `uv.lock`. Run every command via `uv run`.

| Library / Tool | PyPI package | Version | Purpose in this phase |
|---|---|---|---|
| tree-sitter | `tree-sitter` | >=0.22 | Core Python binding shared across all language grammars; run in thread pool executor for CPU-bound parsing |
| tree-sitter-python | `tree-sitter-python` | >=0.22 | Python grammar (carried from Phase 3) |
| tree-sitter-javascript | `tree-sitter-javascript` | >=0.22 | JavaScript/TypeScript grammar; Python binding, thread pool executor |
| tree-sitter-c | `tree-sitter-c` | >=0.22 | C grammar; Python binding, thread pool executor |
| tree-sitter-cpp | `tree-sitter-cpp` | >=0.22 | C++ grammar; Python binding, thread pool executor |
| pyan3 | `pyan3` | >=1.4 | Python call/import graph backend (unchanged from Phase 3); Python API, run in `loop.run_in_executor` |
| lxml | `lxml` | >=5.2 | Parsing XML-format build files (CMake File API output, Ant `build.xml`, Maven POM) |
| defusedxml | `defusedxml` | >=0.7 | Required for all XML from untrusted sources (repository build files, external tool output) |
| orjson | `orjson` | >=3.10 | Backend result serialisation; ctags JSON output parsing |
| ruamel.yaml | `ruamel.yaml` | >=0.18 | Reading CI and build config YAML files; always `YAML(typ='safe')` for untrusted input |
| Pydantic v2 | `pydantic` | >=2.0 | Backend capability models; cross-backend reconciler models; `model_config = ConfigDict(extra="forbid")` on stable contracts |
| SQLModel | `sqlmodel` | >=0.0.21 | Persisting expanded graph facts from new language backends |

**LSP adapters (clangd, Pyright/Pylance, tsserver).** LSP processes are launched and communicated with as subprocesses. In all async code paths this must use `asyncio.create_subprocess_exec`. Never use `subprocess.run` in any `async def` function.

**XML from untrusted sources.** Any CMake File API output, Maven POM, or Ant build file read from a target repository is untrusted. Use `defusedxml` or a hardened `lxml.etree.XMLParser(resolve_entities=False, no_network=True, forbid_dtd=True)` for those paths.

**Backend capability flags.** Missing backends must degrade to partial evidence with a capability-unavailable diagnostic. A missing grammar package or unavailable LSP binary must not break an existing index or suppress unrelated indexing diagnostics. The backend capability registry entry for the missing backend must set `available=False` and record the reason.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 5 depends on:

- Phase 1 schemas:
  - Graph node and edge type enums.
  - Provenance model.
  - Confidence and derivation enums: `parser`, `analyser`, `build`, `test`, `llm`, `heuristic`, `policy`, `review`.
  - Evidence-strength ordering.
  - Snapshot and `git_sha` / worktree-snapshot model.
  - Graph diagnostics model.
- Phase 2 stores:
  - Repository registry.
  - Snapshot ledger.
  - Graph store (add-node, add-edge, fetch by type/ID, fetch by file/span).
  - Artefact registry.
  - Harness metadata store.
- Phase 3 indexing pipeline:
  - `graph_build` and `graph_update` orchestration points.
  - File tree scanner.
  - Git metadata collector.
  - Universal ctags adapter.
  - Tree-sitter adapter.
  - Phase 3 Python AST indexer.
  - Build/test evidence detector.
  - Operational run event writers.
  - Lazy symbol-summary cache invalidation hooks.
- Phase 4 MCP server:
  - `graph_build` and `graph_update` task-capable tools already running.
  - Resource update notification hooks for graph, summary, blame, and build-evidence changes.

### Phase Outputs

Phase 5 should produce:

- `python` backend package hardened with pyan3 call-graph and Pyright/LSP adapter.
- `typescript` backend package with ts-morph, madge, package metadata, and test-runner detection.
- `cpp` backend package with libclang, clangd LSP, compile_commands.json, CMake File API, and CTest.
- `java` backend package stub gated by capability flag.
- `lsp` abstraction package shared by Pyright, clangd, and typescript-language-server adapters.
- Backend capability registry and capability model.
- Cross-backend fact reconciler.
- Incremental update integration for new backends.
- Extended build/test evidence detection for JavaScript/TypeScript and C/C++ build systems.
- Updated fixture repositories for Python, JS/TS, and C/C++.
- Backend-specific error handling and diagnostic schemas.
- Backend capability tests and fixture-level integration tests for each language.

### Non-Goals

Do not implement these in Phase 5:

- Cross-language interface plugin traversal. That is Phase 7.
- SARIF ingestion or alert binding. That is Phase 6.
- Fault localisation ranking. That is Phase 9.
- Repo-QA question answering. That is Phase 8.
- Dynamic tracing. That is Phase 16.
- Full enterprise LSP server management or remote LSP servers.
- Generating code from discovered patterns.
- Auto-fixing import errors or build failures.
- Production authentication for multi-user LSP use.

Phase 5 backends contribute typed graph evidence. They do not interpret or act on that evidence beyond attaching confidence and diagnostics.

---

## 3. Recommended File Layout

Assuming package name `evidence_sca`:

```text
src/evidence_sca/
  indexing/
    backends/
      __init__.py
      base.py
      capability.py
      registry.py
      cross_check.py
      fact_reconciler.py
      diagnostics.py

    backends/python/
      __init__.py
      python_backend.py
      ast_indexer.py
      pyan3_adapter.py
      pyright_adapter.py
      import_resolver.py
      test_detection.py

    backends/typescript/
      __init__.py
      ts_backend.py
      tsmorph_adapter.py
      madge_adapter.py
      package_meta.py
      ts_test_detection.py
      module_resolver.py

    backends/cpp/
      __init__.py
      cpp_backend.py
      libclang_adapter.py
      clangd_adapter.py
      compile_commands.py
      cmake_backend.py
      ctest_detection.py
      abi_edge_builder.py

    backends/java/
      __init__.py
      java_backend.py
      jdt_adapter.py
      capability.py

    lsp/
      __init__.py
      client.py
      protocol.py
      lifecycle.py
      request_dispatcher.py
      capabilities.py
      errors.py

tests/
  indexing/
    backends/
      fixtures/
        python_repo/
          src/
          tests/
          pyproject.toml
          README.md
        typescript_repo/
          src/
          tests/
          package.json
          tsconfig.json
        cpp_repo/
          src/
          tests/
          CMakeLists.txt
          compile_commands.json
        mixed_repo/
          python_module/
          ts_module/
          cpp_module/
      test_backend_base.py
      test_capability.py
      test_backend_registry.py
      test_cross_check.py
      test_fact_reconciler.py
      python/
        test_pyan3_adapter.py
        test_pyright_adapter.py
        test_python_backend.py
        test_import_resolver.py
      typescript/
        test_tsmorph_adapter.py
        test_madge_adapter.py
        test_package_meta.py
        test_ts_test_detection.py
        test_ts_backend.py
      cpp/
        test_compile_commands.py
        test_libclang_adapter.py
        test_clangd_adapter.py
        test_cmake_backend.py
        test_ctest_detection.py
        test_cpp_backend.py
      java/
        test_java_capability.py
      lsp/
        test_lsp_client.py
        test_lsp_lifecycle.py
        test_lsp_protocol.py
```

The existing `indexing/python/` modules from Phase 3 should be migrated or aliased under this structure. Phase 3's `ast_backend.py` becomes the base for `ast_indexer.py`. The Phase 3 ctags and tree-sitter adapters remain shared utilities accessible to all backends.

---

## 4. Backend Architecture Overview

### 4.1 Design Principle

Every language backend is an evidence producer that populates a shared Phase 2 graph store via Phase 1 typed models. Backends have no knowledge of workflows, MCP tools, or LLM calls. They receive a repository descriptor and a snapshot, and produce graph nodes, graph edges, diagnostics, and capability metadata.

```text
BackendInput
  -> BackendPipeline
     -> scanner/parser/LSP/compiler
     -> graph node builder
     -> graph edge builder
     -> diagnostic collector
  -> BackendOutput
     -> nodes : list[GraphNode]
     -> edges : list[GraphEdge]
     -> diagnostics : list[IndexDiagnostic]
     -> capabilities : BackendCapabilityReport
     -> run_stats : BackendRunStats
```

The graph store merge layer handles deduplication and cross-backend reconciliation.

### 4.2 Backend Identifiers

Each backend has a stable identifier used in provenance and diagnostic records:

- `python.ast` — Phase 3 AST-only indexer, still active and default.
- `python.pyan3` — pyan3 call-graph adapter.
- `python.pyright` — Pyright LSP adapter for type and reference facts.
- `typescript.tsmorph` — ts-morph symbol, import, and call analysis.
- `typescript.madge` — madge dependency graph.
- `cpp.libclang` — libclang AST analysis.
- `cpp.clangd` — clangd LSP adapter.
- `cpp.cmake` — CMake File API build evidence.
- `java.jdt` — optional JDT/javac adapter.
- `shared.ctags` — Phase 3 universal ctags adapter, still shared.
- `shared.treesitter` — Phase 3 tree-sitter adapter, still shared.

Backend ID plus backend version string must appear in every provenance record from that backend.

### 4.3 Backend Selection And Priority

At indexing time, the pipeline selects backends based on:

- Repository language hints from Phase 3 file scanner.
- Detected build files and language markers.
- Backend availability check result.
- Phase 3 backend config from `IndexConfig`.

Multiple backends may contribute to the same file or symbol. Merge and reconciliation is handled downstream.

### 4.4 Baseline Rule

If no language-specific backend is available for a file, the Phase 3 ctags adapter and tree-sitter adapter remain as the baseline. A file must never return zero nodes because a language-specific backend failed. Backend failure is a diagnostic, not a silent drop.

---

## 5. Backend Base Interface

### 5.1 `BackendBase`

Recommended abstract interface:

```text
BackendBase
  backend_id : str
  backend_version : str

  check_availability() -> BackendAvailability
    # Check required external tools/libs/runtimes are present.
    # Must not run analysis.

  describe_capabilities() -> BackendCapabilityDescriptor
    # Return what node types, edge types, and confidence levels
    # this backend can produce.

  index_repo(
    repo: RepositoryRecord,
    snapshot: SnapshotDescriptor,
    files: list[RepoRelativePath] | None,
    config: BackendConfig,
  ) -> BackendOutput
    # Index all or specified files.
    # Must not mutate the graph store directly.
    # Must not raise unchecked exceptions.
    # Must return diagnostics instead of raising on individual file errors.

  supports_incremental() -> bool
    # Return True only if index_files can skip unchanged files safely.

  index_files(
    repo: RepositoryRecord,
    snapshot: SnapshotDescriptor,
    changed_files: list[RepoRelativePath],
    prior_output_ref: ArtifactRef | None,
    config: BackendConfig,
  ) -> BackendOutput
    # Incremental re-index of changed files.
    # Only called when supports_incremental() is True.
```

### 5.2 `BackendOutput`

Recommended output model:

```text
BackendOutput
  backend_id : str
  backend_version : str
  repo_id : str
  snapshot_id : str
  git_sha : str | None
  worktree_snapshot_id : str | None
  nodes : list[GraphNode]
  edges : list[GraphEdge]
  diagnostics : list[IndexDiagnostic]
  skipped_files : list[SkippedFile]
  capabilities_used : list[str]
  run_stats : BackendRunStats
  output_hash : str
```

All nodes and edges must include `repo`, `git_sha`, optionally `worktree_snapshot_id`, `file`, `span`, `confidence`, and `derivation` as required by Phase 1 provenance rules.

### 5.3 `BackendAvailability`

```text
BackendAvailability
  backend_id : str
  available : bool
  tool_path : str | None
  tool_version : str | None
  missing_deps : list[str]
  warnings : list[str]
```

Availability checks must be fast and side-effect-free.

### 5.4 `BackendRunStats`

```text
BackendRunStats
  files_scanned : int
  files_skipped : int
  files_failed : int
  nodes_emitted : int
  edges_emitted : int
  diagnostics_emitted : int
  wall_ms : int
  peak_memory_mb : float | None
```

---

## 6. Backend Capability Model

### 6.1 Purpose

Each backend reports the evidence it can contribute so that the graph store, cross-checker, and downstream consumers can reason about evidence completeness.

### 6.2 `BackendCapabilityDescriptor`

```text
BackendCapabilityDescriptor
  backend_id : str
  backend_version : str
  supported_node_types : list[GraphNodeType]
  supported_edge_types : list[GraphEdgeType]
  max_confidence : ConfidenceLevel
  derivation : DerivationSource
  can_resolve_cross_file_calls : bool
  can_resolve_cross_module_calls : bool
  can_produce_type_edges : bool
  can_produce_nullness_edges : bool
  can_produce_dataflow_edges : bool
  can_index_generated_files : bool
  requires_compile_commands : bool
  requires_build_artifacts : bool
  incremental_support : bool
  lsp_based : bool
  languages : list[str]
```

### 6.3 Registry

The backend registry maps language hints and file extensions to candidate backends, ordered by priority. When multiple backends can serve a file type, all are run and their outputs are merged through the fact reconciler.

Recommended registry query interface:

```text
BackendRegistry
  register(backend: BackendBase) -> None
  available_backends(language: str) -> list[BackendBase]
  capability_report() -> list[BackendCapabilityDescriptor]
  availability_check() -> list[BackendAvailability]
```

### 6.4 Capability Tests

Required tests:

- Registry lists all registered backends.
- Each backend returns a non-empty capability descriptor.
- Availability check does not run analysis.
- Unavailable backend is marked unavailable without crashing.
- Capability report is stable under snapshot tests.

---

## 7. Python Backend Hardening

### 7.1 Phase 3 Baseline

Phase 3 built a Python MVP with AST-based symbol and import indexing, ctags, and tree-sitter. Phase 5 adds:

- `pyan3` call-graph adapter.
- Pyright or generic Python LSP adapter for type-aware references and diagnostics.

The Phase 3 AST indexer remains active and provides the baseline symbol/import graph. The Phase 5 additions augment call edges and raise confidence for specific node/edge types.

### 7.2 `pyan3` Call-Graph Adapter

`pyan3` performs static analysis of Python code and produces a directed call graph without executing the program.

Adapter responsibilities:

- Run `pyan3` as a subprocess or use its programmatic API against the repo root.
- Parse `pyan3` JSON or dot output.
- Map pyan3 module/function identifiers to Phase 3 AST-derived symbol node IDs.
- Emit `calls` edges with `derivation=analyser`, `confidence=parser` where pyan3 resolves callee identity statically, and `confidence=heuristic` for dynamic or ambiguous calls.
- Emit `contains` edges for module-to-function relationships not already present.
- Record unresolvable call sites as diagnostics, not dropped.

Availability check:

- Check that `pyan3` is importable or `pyan3` CLI is on PATH.
- Check that the repo has Python source files discoverable by pyan3.

pyan3 known limitations to document:

- Does not resolve all dynamic dispatch patterns.
- May miss calls through decorators that obscure the call target.
- Requires the repo to be importable or run from the repo root.
- May produce multiple candidate callees for polymorphic calls.

Phase 5 treatment: ambiguous call targets become multiple low-confidence `calls` edges rather than a single high-confidence edge or no edge.

### 7.3 Pyright LSP Adapter

Pyright provides precise type-level references and diagnostics when run as a language server.

Adapter responsibilities:

- Start Pyright as a language server via the shared LSP abstraction layer.
- Negotiate capabilities on connection.
- For each Python file, request:
  - `textDocument/documentSymbol` for symbol hierarchy.
  - `textDocument/references` for incoming references to key symbols.
  - `textDocument/definition` for definition resolution.
  - `textDocument/diagnostic` for static type errors.
- Map LSP symbol kinds to Phase 1 graph node types.
- Map references to `calls`, `imports`, or `instantiates` edges depending on context.
- Attach Pyright diagnostics as `sast_rule`-like graph nodes linked via `warned_by` edges.
- Emit `derivation=analyser` for LSP-derived facts.
- Emit `confidence=parser` where Pyright resolves symbols precisely via type checking.
- Emit `confidence=heuristic` for partially resolved or overloaded references.

Availability check:

- Check that `pyright-langserver` binary is on PATH or that `pyright` package is importable.
- Check for `pyrightconfig.json` or `pyproject.toml` with `[tool.pyright]` section.
- If missing, report as unavailable and fall back to pyan3-only.

Pyright known limitations to document:

- Requires project configuration for stub packages and virtual environments.
- May time out or produce incomplete results for very large repos.
- Does not handle all dynamic attribute access patterns.

### 7.4 Python Backend Unification

`python_backend.py` orchestrates the three Python sub-backends:

1. `python.ast` (Phase 3 baseline) — always runs first.
2. `python.pyan3` — runs when available, augments `calls` edges.
3. `python.pyright` — runs when available, augments type and reference edges.

Merge order: AST facts form the base; pyan3 call edges are added with reconciliation; Pyright type/reference edges are added at highest confidence.

The Phase 3 `import_resolver.py` is refactored into a shared `ImportResolver` used by all three sub-backends.

### 7.5 Python Backend Tests

Required tests:

- AST indexer produces symbols and imports for fixture Python repo.
- pyan3 adapter produces `calls` edges for fixture repo.
- pyan3 unresolvable call site becomes diagnostic, not edge.
- Pyright adapter availability check works with and without Pyright installed.
- Pyright LSP adapter produces type-reference edges for fixture with Pyright present.
- Pyright diagnostic becomes graph node with `warned_by` edge.
- Python backend merge produces higher-confidence call edges where sources agree.
- pyan3 unavailable degrades to AST-only without error.
- Pyright unavailable degrades without error.
- Provenance on every emitted node/edge includes `backend_id` and `backend_version`.

---

## 8. JavaScript/TypeScript Backend

### 8.1 Purpose

The TypeScript backend targets JavaScript and TypeScript repositories. It uses ts-morph (TypeScript Compiler API wrapper) for accurate symbol, import, and call analysis, and madge for dependency graph construction.

### 8.2 Prerequisites

External requirements:

- Node.js and npm available on PATH.
- `ts-morph` npm package installed in a managed node_modules location known to the adapter.
- `madge` npm package installed similarly.
- TypeScript itself (`typescript` npm package) where a project-level tsconfig.json exists.

The adapter should use a small fixed runner script (checked in) rather than dynamically generated scripts to avoid code-injection risk. The runner script accepts a JSON config on stdin and writes JSON output to stdout.

### 8.3 `ts-morph` Adapter

`tsmorph_adapter.py` launches a Node.js runner script that uses the ts-morph API to extract:

- File nodes for each scanned TypeScript/JavaScript file.
- Module nodes for namespace and module declarations.
- Class, function, method, variable, type, and interface nodes.
- Import edges for each `import` statement, with resolved file path when resolvable.
- Calls edges for function/method calls where ts-morph resolves the callee.
- Instantiates edges for `new` expressions where ts-morph resolves the class.
- TypeScript-specific interface/type structure edges under `type` and `interface` node types.

Confidence rules:

- `confidence=parser`, `derivation=analyser` for TypeScript files where the compiler can type-check fully.
- `confidence=heuristic` for JavaScript files without type information.
- `confidence=heuristic` for dynamic imports (`import()`) and computed property accesses.

The runner script output schema must match a stable JSON contract between the Python adapter and the Node.js runner. Changes to the runner script must be covered by adapter snapshot tests.

### 8.4 `madge` Adapter

`madge_adapter.py` launches a Node.js process running `madge` to produce a flat dependency graph.

Extracts:

- Module dependency edges (`imports`/`contains`) as a cross-check source against ts-morph.
- Circular dependency groups as diagnostics.
- Files with no inbound imports as orphan diagnostics.

Confidence rules:

- `confidence=heuristic`, `derivation=analyser` for all madge-derived edges.
- madge edges are used as cross-check candidates against ts-morph edges, not as primary graph data.

### 8.5 Package Metadata

`package_meta.py` parses `package.json` and `package-lock.json` or `yarn.lock` where present.

Extracts:

- Package name and version as repo-level metadata.
- `dependencies` and `devDependencies` as build-evidence graph nodes.
- Script keys (`test`, `lint`, `build`) as build-target nodes.
- Workspace configuration for monorepo detection.

Emits:

- `build_target` nodes for relevant scripts.
- Dependency version provenance metadata.

### 8.6 Test-Runner Detection

`ts_test_detection.py` detects JavaScript/TypeScript test runners.

Detection sources:

- `jest.config.*` files.
- `vitest.config.*` files.
- `mocha` and `.mocharc.*` files.
- `karma.conf.*` files.
- `jasmine.json` or `spec/support/jasmine.json`.
- `package.json` `jest`, `mocha`, and `vitest` sections.
- `package.json` `scripts.test` patterns.

Emits:

- `ci_job` or `build_target` nodes for detected test commands.
- Test-directory evidence linked to `tests` nodes.
- Confidence is `heuristic` because test execution is not verified.

### 8.7 TypeScript/JavaScript Backend Unification

`ts_backend.py` orchestrates:

1. `typescript.tsmorph` — primary symbol/import/call analysis.
2. `typescript.madge` — dependency graph cross-check.
3. Package metadata from `package_meta.py`.
4. Test-runner detection from `ts_test_detection.py`.

When ts-morph is unavailable, fall back to tree-sitter and ctags for TypeScript/JavaScript files, and record degraded capability in diagnostics.

### 8.8 JavaScript/TypeScript Backend Tests

Required tests:

- ts-morph adapter produces file, class, function, and import nodes for fixture TypeScript repo.
- ts-morph produces `calls` edges for direct function invocations.
- Unresolvable dynamic import becomes diagnostic edge candidate.
- madge produces dependency edges cross-checkable against ts-morph.
- madge circular dependency becomes diagnostic.
- Package metadata parser extracts name, version, and test script.
- Test-runner detection returns jest/vitest/mocha evidence for fixture repos.
- ts-morph unavailable degrades to tree-sitter/ctags with capability diagnostic.
- Runner script output is stable under snapshot tests.
- Node.js not found is an availability diagnostic, not a crash.

---

## 9. C/C++ Backend

### 9.1 Purpose

The C/C++ backend requires a compilation database to resolve include paths and compiler flags. Without it, analysis degrades to ctags and tree-sitter baseline. With it, libclang and clangd provide precise AST and reference evidence.

### 9.2 Compilation Database

`compile_commands.py` parses `compile_commands.json` as the entry point for C/C++ analysis.

Parsing responsibilities:

- Load and validate the JSON array of compilation records.
- Normalize file paths relative to the repo root.
- Extract include directories, defines, and language standard flags.
- Detect files in the repo that are not listed in `compile_commands.json` as partial-coverage diagnostics.
- Record the command generation tool if identifiable (`cmake`, `bear`, `ninja`, etc.).

`compile_commands.json` may not be present. When absent:

- Mark C/C++ backend capability as `degraded_no_compile_commands`.
- Fall back to ctags and tree-sitter.
- Emit diagnostic recommending `bear` or CMake.

### 9.3 `libclang` Adapter

`libclang_adapter.py` uses the `libclang` Python bindings or the `clang` package to parse translation units.

Extracts:

- File nodes per source file.
- Class, struct, function, method, and variable nodes.
- Include edges (`imports`) for `#include` directives, resolved to repo-relative paths where possible.
- Calls edges for static call sites resolvable at AST level.
- Ownership/struct-member edges under `owns`.
- Nullness edges for pointer parameters and return types where expressible.
- Template instantiation edges under `instantiates` where resolvable.

Confidence rules:

- `confidence=parser`, `derivation=parser` for libclang-resolved symbols and includes.
- `confidence=heuristic` for function pointers and virtual dispatch.
- `confidence=heuristic` for template specializations not fully resolvable at parse time.

libclang limitations to document:

- Requires `compile_commands.json` or per-file compilation flags for accurate analysis.
- Template metaprogramming may produce incomplete ASTs.
- Header-only analysis without a consuming translation unit may miss some facts.
- Cross-TU call analysis requires libclang index operations that are expensive.

### 9.4 `clangd` LSP Adapter

`clangd_adapter.py` uses the shared LSP abstraction layer to communicate with `clangd`.

Extracts:

- `textDocument/references` for call-site cross-checking.
- `textDocument/definition` for definition resolution.
- `textDocument/diagnostic` for clangd diagnostics.
- `workspace/symbol` for symbol lookup.

Confidence rules:

- `confidence=parser` for clangd-resolved cross-file references.
- Clangd diagnostics become `sast_rule` nodes linked via `warned_by` edges.

Availability:

- Check `clangd` binary version.
- Require `compile_commands.json` or fall back to unavailable.

### 9.5 CMake File API Integration

`cmake_backend.py` queries the CMake File API if a CMake build directory is present.

Extracts:

- CMake targets as `build_target` nodes.
- Target-to-source-file membership.
- Compile definitions and include directories.
- Test executable targets.

Availability:

- Check for `CMakeLists.txt` in repo.
- Check for configured build directory with `.cmake/api/v1/` present.
- Fall back gracefully if no configured build directory exists.

### 9.6 CTest Detection

`ctest_detection.py` detects CTest configuration.

Detection sources:

- `CTestTestfile.cmake` in build directory.
- `enable_testing()` and `add_test()` calls in `CMakeLists.txt`.
- `ctest` binary presence.

Emits:

- `ci_job` or `build_target` nodes for CTest commands.
- Test executable nodes linked to their sources where resolvable.

### 9.7 ABI Edge Builder

`abi_edge_builder.py` constructs ABI-relevant edges for public C/C++ API symbols.

Extracts from libclang AST:

- Exported symbols (public class methods, global functions, extern declarations).
- Template parameter lists for template-specialized edge candidates.
- `[[nodiscard]]`, `noexcept`, and `const` qualifiers as edge annotations.

These edges support Phase 15 blast-radius ABI impact analysis.

### 9.8 C/C++ Backend Unification

`cpp_backend.py` orchestrates:

1. Compile-commands loading and validation.
2. `cpp.libclang` — primary AST analysis.
3. `cpp.clangd` — LSP reference and diagnostic augmentation.
4. `cpp.cmake` — build target evidence.
5. CTest detection.
6. ABI edge construction.

Degradation ladder:

- Full: `compile_commands.json` + libclang + clangd + CMake.
- Partial: `compile_commands.json` + libclang only.
- Minimal: ctags + tree-sitter only, with capability diagnostic.

### 9.9 C/C++ Backend Tests

Required tests:

- Compile-commands parser handles fixture `compile_commands.json`.
- Missing `compile_commands.json` produces capability diagnostic, not crash.
- libclang adapter produces symbols and includes for fixture C/C++ repo.
- libclang function-pointer call becomes heuristic-confidence edge.
- clangd adapter availability check passes when clangd is installed.
- clangd diagnostic becomes `warned_by` edge node.
- CMake File API parser extracts targets from fixture build directory.
- CTest detection returns test commands for fixture CMake repo.
- ABI edge builder marks public symbols.
- C/C++ backend degrades gracefully with each missing dependency.
- Backend run stats report files scanned and failed.

---

## 10. Optional Java Backend

### 10.1 Purpose

The Java backend enables calibration on Vul4J, SWE-PolyBench-style, or customer corpora. It is off by default.

### 10.2 Capability Flag

`java/capability.py` exports:

```text
JAVA_BACKEND_ENABLED : bool
  # Controlled by config key indexing.backends.java.enabled
  # Default: False
```

All Java backend code paths must check this flag before running. If disabled, the backend reports unavailable and produces no diagnostics that would confuse the index.

### 10.3 `jdt_adapter.py`

Phase 5 implements a minimal JDT or `javac`-based adapter:

- Use `javac -Xlint` output or a small JDT-based analysis script as a subprocess.
- Extract class, method, field, and import nodes.
- Extract `calls` edges from method invocations where resolvable.
- Requires `JAVA_HOME` or `java` on PATH.

Full JDT or CodeQL Java integration can be deferred. Phase 5 delivers a working capability check and a fixture-level integration path so that Java calibration fixtures can run when the flag is enabled.

### 10.4 Java Backend Tests

Required tests:

- Java capability flag defaults to False.
- Java backend availability check returns unavailable when flag is False.
- When flag is True and JDK is present, Java fixture produces class and method nodes.
- Java backend disabled does not affect Python/TS/C++ indexing.

---

## 11. LSP Abstraction Layer

### 11.1 Purpose

Pyright, clangd, and typescript-language-server (for enhanced TS analysis) all speak JSON-RPC over stdio. A shared LSP abstraction prevents three independent subprocess-management implementations and three independent timeout/retry handling implementations.

### 11.2 `LspClient`

Recommended interface:

```text
LspClient
  server_id : str
  cmd : list[str]
  workspace_path : Path
  capabilities : LspClientCapabilities

  start() -> None
    # Launch the server process.
    # Send initialize request.
    # Await initialized notification.

  stop() -> None
    # Send shutdown request.
    # Send exit notification.
    # Terminate process.

  request(method: str, params: dict, timeout_ms: int) -> dict
    # Send request and await response.
    # Raise LspTimeout or LspError on failure.

  notify(method: str, params: dict) -> None
    # Send notification (no response expected).

  open_document(uri: str, language_id: str, text: str) -> None
    # Send textDocument/didOpen.

  close_document(uri: str) -> None
    # Send textDocument/didClose.
```

### 11.3 `LspLifecycle`

`lifecycle.py` manages server process start/stop, crash recovery, and timeout.

Rules:

- LSP server must be stopped on adapter exit, even on exception.
- If the server crashes mid-session, mark remaining requests as failed and emit diagnostics.
- Do not leave zombie processes.
- Server lifecycle log entries must use the operational event format.

### 11.4 `RequestDispatcher`

`request_dispatcher.py` handles JSON-RPC request/response matching.

Rules:

- Match responses to requests by `id`.
- Queue notifications received before their matching request.
- Emit diagnostics for malformed responses.
- Enforce per-request timeout independently.

### 11.5 `LspCapabilities`

`capabilities.py` holds the client capability declaration sent on `initialize` and parses the server's returned capabilities.

Rules:

- Declare minimal client capabilities required for each adapter's needs.
- Do not declare capabilities the adapter does not use.
- Record server capabilities in `BackendCapabilityDescriptor`.

### 11.6 LSP Client Tests

Required tests:

- `LspClient` starts and stops a mock server process.
- Request/response round-trip works.
- Timeout on slow response raises `LspTimeout`.
- Server crash marks session failed.
- Process lifecycle does not leave zombies.
- Document open/close sends correct notifications.
- Capability negotiation records server capabilities.

---

## 12. Cross-Backend Fact Reconciliation

### 12.1 Purpose

Multiple backends may contribute overlapping or conflicting facts about the same symbol or edge. The cross-checker and fact reconciler produce a unified view with evidence strength metadata rather than silently picking a winner.

### 12.2 Evidence Agreement Model

For each graph fact, track which backends contributed it and whether they agree:

```text
EvidenceAgreement
  fact_id : str
  fact_type : str
  contributing_backends : list[str]
  agreement : AgreementState
    # confirmed   - multiple independent sources agree
    # candidate   - single source only
    # conflicting - sources disagree on target or type
  merged_confidence : ConfidenceLevel
  merged_derivation : DerivationSource
  conflict_notes : list[str]
```

`AgreementState` rules:

- `confirmed`: two or more backends agree on the fact's key fields.
- `candidate`: only one backend emits the fact.
- `conflicting`: two or more backends emit mutually exclusive versions of the fact.

### 12.3 `CrossChecker`

`cross_check.py` compares backend outputs before merging into the graph store.

Rules:

- ctags symbol without matching AST or LSP symbol: `candidate` with `confidence=heuristic`.
- AST symbol confirmed by Pyright/LSP: upgrade to `confidence=parser`, `confirmed`.
- pyan3 call edge confirmed by Pyright reference: `confidence=parser`, `confirmed`.
- pyan3 call edge with no LSP confirmation: `candidate`, `confidence=heuristic`.
- ts-morph import confirmed by madge: `confidence=parser`, `confirmed`.
- Conflicting call targets from two sources: both emitted as `conflicting` edges with lower confidence.

### 12.4 `FactReconciler`

`fact_reconciler.py` applies the agreement model to produce the final node and edge set submitted to the graph store.

Steps:

1. Collect all backend outputs for a given snapshot.
2. Group facts by canonical identifier.
3. Apply `CrossChecker` to compute `EvidenceAgreement` per fact.
4. Produce merged `GraphNode` and `GraphEdge` with `EvidenceAgreement` metadata.
5. Emit reconciliation diagnostics for conflicts.
6. Submit merged facts to Phase 2 graph store.

Rules:

- Conflicting facts must not be merged into a single confident fact.
- A `conflicting` edge must be stored as two separate low-confidence edges, not one.
- Reconciler diagnostics count toward the index diagnostic summary.
- Mixed-confidence nodes must carry the lowest-confidence source's annotation.

### 12.5 Cross-Check Tests

Required tests:

- Two backends agree on a function symbol: produces `confirmed`, `confidence=parser`.
- One backend emits a call edge: produces `candidate`, `confidence=heuristic`.
- Two backends emit conflicting call targets: produces two `conflicting` edges.
- Reconciler diagnostics are emitted for each conflict.
- Merged nodes carry provenance from all contributing backends.
- Fact reconciler is deterministic given the same backend outputs.

---

## 13. Build And Test Evidence Integration

### 13.1 Expanding Phase 3 Detection

Phase 3 detected pytest and package manager files. Phase 5 extends this to JavaScript/TypeScript and C/C++ build systems.

### 13.2 JavaScript/TypeScript Build Evidence

Detected from:

- `package.json` `scripts.test`, `scripts.build`, `scripts.lint`.
- `jest.config.*`, `vitest.config.*`, `.mocharc.*`.
- `webpack.config.*`, `vite.config.*`, `esbuild.config.*`.
- `tsconfig.json` and `tsconfig.build.json`.
- `yarn.lock`, `package-lock.json`, `pnpm-lock.yaml`.

Emits:

- `build_target` nodes for build/test scripts.
- `ci_job` nodes for known CI-triggerable scripts.
- Package manager provenance as `build_target` metadata.

### 13.3 C/C++ Build Evidence

Detected from:

- `CMakeLists.txt`.
- `Makefile`.
- `meson.build`.
- `Bazel` BUILD or WORKSPACE files.
- `compile_commands.json`.
- `CTestTestfile.cmake` in build directories.
- `.cmake/api/v1/` CMake File API directory.

Emits:

- `build_target` nodes for each detected build target.
- `ci_job` nodes for CTest execution.
- Build system type as metadata.

### 13.4 Tests

Required tests:

- JavaScript build evidence returns jest and build script nodes for fixture.
- TypeScript tsconfig present produces build target node.
- C/C++ CMake build evidence returns cmake targets.
- C/C++ Makefile detected as fallback build evidence.
- Missing build system produces empty evidence with diagnostic, not error.

---

## 14. Confidence And Provenance Rules

### 14.1 Evidence Hierarchy

All Phase 5 backend outputs must respect the Phase 1 evidence-strength ordering:

```text
hard static evidence      (parser, confirmed multi-source)
  > structured repo evidence (analyser, single high-quality source)
    > calibrated model evidence (heuristic, cross-checked)
      > soft LLM evidence (never from these backends)
```

### 14.2 Rules Per Backend Type

- **AST-derived facts** (Python ast, libclang, ts-morph): `derivation=parser`.
  - Confidence `parser` where type resolution is complete.
  - Confidence `heuristic` where resolution is partial or dynamic.

- **Call-graph tool facts** (pyan3, madge): `derivation=analyser`.
  - Confidence `parser` where cross-checked by LSP.
  - Confidence `heuristic` where single-source.

- **LSP-derived facts** (Pyright, clangd): `derivation=analyser`.
  - Confidence `parser` for type-checked references.
  - Confidence `heuristic` for overloaded or partially resolved references.

- **Build/test detection**: `derivation=heuristic`.
  - Confidence `heuristic` unless execution evidence exists.

- **ctags / tree-sitter baseline**: `derivation=parser`, `confidence=heuristic` (coarser precision than AST or LSP).

### 14.3 Provenance Fields

Every node and edge must carry:

- `repo_id`
- `git_sha` or `worktree_snapshot_id`
- `file` (repo-relative path)
- `span` where available
- `confidence`
- `derivation`
- `backend_id`
- `backend_version`

Missing provenance fields must fail Phase 1 validation and produce a diagnostic rather than silently storing an under-specified fact.

---

## 15. Backend Degradation And Error Handling

### 15.1 Degradation Hierarchy

For each language target, define explicit degradation levels:

**Python:**

- Full: `python.ast` + `python.pyan3` + `python.pyright`.
- Partial: `python.ast` + `python.pyan3` (Pyright unavailable).
- Minimal: `python.ast` only (pyan3 unavailable).
- Baseline: ctags + tree-sitter (ast unavailable, unusual).

**JavaScript/TypeScript:**

- Full: `typescript.tsmorph` + `typescript.madge` + package metadata.
- Partial: `typescript.tsmorph` only.
- Minimal: ctags + tree-sitter.

**C/C++:**

- Full: `cpp.libclang` + `cpp.clangd` + `cpp.cmake`.
- Partial: `cpp.libclang` only.
- Minimal: ctags + tree-sitter.

### 15.2 Per-File Error Handling

Rules:

- A single-file parse error must produce a diagnostic and skip that file, not abort the whole backend run.
- LSP server crash mid-session must mark all pending file requests as failed with diagnostic.
- External tool timeout must produce a per-file diagnostic with elapsed time.
- A binary or generated file skipped by a backend must appear in `skipped_files` with reason.

### 15.3 Diagnostic Schema

`IndexDiagnostic` already defined in Phase 1. Phase 5 adds diagnostic codes:

- `BACKEND_UNAVAILABLE` — required binary/library not found.
- `BACKEND_VERSION_MISMATCH` — found but incompatible version.
- `BACKEND_DEGRADED` — running in partial mode, expected capability unavailable.
- `COMPILE_COMMANDS_MISSING` — C/C++ analysis degraded.
- `FILE_PARSE_ERROR` — individual file could not be parsed.
- `LSP_TIMEOUT` — LSP request timed out.
- `LSP_CRASH` — LSP server crashed.
- `CROSS_CHECK_CONFLICT` — backends produced conflicting facts.
- `RUNNER_SCRIPT_ERROR` — Node.js runner exited with non-zero code.
- `CALL_TARGET_UNRESOLVED` — call edge candidate emitted as heuristic.

### 15.4 Tests

Required tests:

- Backend with missing tool reports `BACKEND_UNAVAILABLE` diagnostic.
- Single-file parse error produces diagnostic and skips file.
- LSP server crash marks session failed with diagnostic.
- External tool timeout produces per-file diagnostic.
- Binary file correctly skipped with reason.

---

## 16. Incremental Update Integration

### 16.1 Integration Points

Phase 3 built incremental update through the `graph_update` pipeline. Phase 5 backends must integrate with it.

### 16.2 Incremental Support Per Backend

- `python.ast`: supports incremental (re-indexes changed Python files).
- `python.pyan3`: partial incremental; pyan3 may re-analyze the whole module graph. Phase 5 allows full-module re-run on change, recording re-analysis scope in stats.
- `python.pyright`: LSP-based incremental via document sync; Phase 5 uses `textDocument/didChange` for changed files.
- `typescript.tsmorph`: ts-morph supports project-level incremental via `createSourceFile` diff.
- `typescript.madge`: always re-run on dependency file change (fast enough for most repos).
- `cpp.libclang`: re-parse only changed translation units.
- `cpp.clangd`: LSP-based incremental via document sync.

### 16.3 Invalidation Rules

When a file changes, the following must be invalidated:

- All graph nodes and edges derived solely from that file.
- Summary cache entries for symbols in that file.
- Any cross-check agreement records citing that file.
- Blame records for that file (re-fetch).

Nodes and edges from other backends that reference the changed file must be re-evaluated, not silently retained.

### 16.4 Snapshot Consistency

Rules:

- Incremental updates emit the new snapshot ID on all new/updated nodes and edges.
- Old snapshot nodes/edges from the same file must be marked superseded.
- Mixed-snapshot queries remain detectable as in Phase 3.

### 16.5 Tests

Required tests:

- Python backend incremental update after file change updates only changed symbols.
- Summary cache entries for changed file are invalidated.
- C/C++ backend incremental update re-indexes changed translation unit.
- Old-snapshot nodes are marked superseded after incremental update.
- Mixed-snapshot state is detectable.

---

## 17. Fixture Repositories And Test Data

### 17.1 Requirements

Each language backend requires a fixture repository sufficient to exercise the backend's key extraction paths.

### 17.2 Python Fixture (Existing, Extended)

The Phase 3 fixture is extended to include:

- Multiple Python modules with cross-module function calls (for pyan3).
- Type-annotated functions (for Pyright).
- An `__init__.py` import chain.
- A pytest test module that calls into the main modules.
- A `pyproject.toml` and `pyrightconfig.json`.

### 17.3 TypeScript Fixture

Requirements:

- At least three TypeScript source files with class definitions, imports, and method calls.
- At least one JavaScript file without types.
- A `package.json` with test script.
- A `tsconfig.json`.
- A jest or vitest config.
- A dependency on a local module (for import resolution).

### 17.4 C/C++ Fixture

Requirements:

- At least three C++ source files with class definitions, includes, and function calls.
- A header file.
- A `CMakeLists.txt` with at least one target and CTest.
- A `compile_commands.json` (pre-generated for the fixture).
- A Makefile for fallback detection.
- A test executable source file.

### 17.5 Mixed-Language Fixture

Requirements:

- Python module and a small C extension (for Python-C calling pattern).
- Or a TypeScript frontend and Python backend sharing an interface definition.
- Used in Phase 7 interface plugin tests.

Phase 5 creates the fixture; Phase 7 adds the cross-language linking.

### 17.6 Fixture Commit Rules

- Fixture repositories must be committed as subdirectories under `tests/indexing/backends/fixtures/`.
- Fixture repositories must not contain real secrets.
- Pre-generated `compile_commands.json` must be kept in sync with the fixture `CMakeLists.txt`.
- Fixture README explains what each fixture exercises.

---

## 18. Test Plan

### 18.1 Backend Base Tests

Required:

- `BackendBase` concrete subclasses pass interface contract tests.
- `check_availability` is fast and side-effect-free.
- `index_repo` with empty file list returns empty output without error.
- `BackendOutput` validates against Phase 1 models.

### 18.2 Capability Tests

Required:

- Each backend capability descriptor lists supported node/edge types.
- Capability descriptor is stable under snapshot tests.
- Registry capability report includes all registered backends.
- Availability check reports unavailable when tool is missing.

### 18.3 Python Backend Tests

Required:

- AST indexer: symbols, imports, and spans for fixture Python repo.
- pyan3 adapter: `calls` edges for fixture repo.
- pyan3 unresolvable call: diagnostic, not dropped edge.
- Pyright adapter: type-reference edges when Pyright is available.
- Pyright diagnostic: `warned_by` edge node.
- Python backend merge: higher-confidence call edges where sources agree.
- Degradation: pyan3 unavailable, Pyright unavailable both degrade correctly.

### 18.4 TypeScript Backend Tests

Required:

- ts-morph adapter: file, class, function, import nodes for fixture TS repo.
- ts-morph `calls` edges for direct invocations.
- ts-morph dynamic import becomes diagnostic.
- madge adapter: dependency edges cross-checkable against ts-morph.
- madge circular dependency: diagnostic.
- Package metadata: name, version, test script.
- Test-runner detection: jest/vitest evidence from fixture.
- Degradation: Node.js unavailable degrades gracefully.

### 18.5 C/C++ Backend Tests

Required:

- `compile_commands.json` parser: correct flags and file coverage.
- Missing `compile_commands.json`: capability diagnostic.
- libclang adapter: symbols, includes, and calls for fixture.
- libclang function pointer: heuristic-confidence edge.
- clangd adapter: cross-file reference edge.
- clangd diagnostic: `warned_by` node.
- CMake File API: build targets from fixture.
- CTest detection: test commands.
- ABI edge builder: public symbol marking.
- Degradation ladder: full, partial, minimal each produce expected capability diagnostics.

### 18.6 Java Backend Tests

Required:

- Capability flag defaults to False.
- Backend unavailable when flag is False.
- Java fixture produces class and method nodes when flag is True and JDK is present.

### 18.7 LSP Tests

Required:

- `LspClient` start/stop with mock server.
- Request/response round-trip.
- Timeout raises `LspTimeout`.
- Server crash marks session failed.
- No zombie processes.
- Capability negotiation records server capabilities.

### 18.8 Cross-Check And Reconciliation Tests

Required:

- Two backends agree: `confirmed` state, `confidence=parser`.
- Single backend: `candidate` state, `confidence=heuristic`.
- Two backends conflict: two `conflicting` edges, diagnostics emitted.
- Reconciler is deterministic.
- Merged nodes carry provenance from all contributors.

### 18.9 Incremental Update Tests

Required:

- Python backend incremental after file change: updated symbols, invalidated summaries.
- C/C++ incremental after source change: re-indexed TU.
- Old-snapshot nodes superseded.
- Mixed-snapshot detectable.

### 18.10 Regression Tests

Required:

- Backend capability descriptor snapshots.
- Backend output schema validation for each fixture.
- Diagnostic code coverage per degradation scenario.
- Cross-check output snapshot for fixture Python repo.

---

## 19. Work Packages

### P5.1 Backend Base Interface And Capability Model

Build:

- `BackendBase` abstract class.
- `BackendOutput` model.
- `BackendAvailability` model.
- `BackendCapabilityDescriptor` model.
- `BackendRunStats` model.
- Backend registry.

Deliverables:

- `indexing/backends/base.py`
- `indexing/backends/capability.py`
- `indexing/backends/registry.py`
- Base and capability tests.

Acceptance:

- Interface contract tests pass for a no-op test backend.

### P5.2 Python Backend Hardening

Build:

- `pyan3` adapter.
- Pyright LSP adapter using shared LSP client.
- Python backend orchestrator.
- Extended import resolver.

Deliverables:

- `indexing/backends/python/pyan3_adapter.py`
- `indexing/backends/python/pyright_adapter.py`
- `indexing/backends/python/python_backend.py`
- `indexing/backends/python/import_resolver.py`
- Python backend tests.

Acceptance:

- pyan3 call edges appear in fixture Python graph.
- Pyright diagnostic nodes linked via `warned_by`.

### P5.3 LSP Abstraction Layer

Build:

- `LspClient` class.
- `LspLifecycle` process management.
- `RequestDispatcher` JSON-RPC matching.
- `LspCapabilities` model.
- Error types.

Deliverables:

- `indexing/lsp/client.py`
- `indexing/lsp/protocol.py`
- `indexing/lsp/lifecycle.py`
- `indexing/lsp/request_dispatcher.py`
- `indexing/lsp/capabilities.py`
- `indexing/lsp/errors.py`
- LSP tests.

Acceptance:

- Mock LSP server round-trip passes.
- No zombie processes on crash.

### P5.4 TypeScript/JavaScript Backend

Build:

- ts-morph Node.js runner script.
- `tsmorph_adapter.py` Python adapter.
- `madge_adapter.py`.
- `package_meta.py`.
- `ts_test_detection.py`.
- `ts_backend.py` orchestrator.

Deliverables:

- `indexing/backends/typescript/`
- Node.js runner scripts.
- TS fixture repository.
- TypeScript backend tests.

Acceptance:

- ts-morph produces typed symbol and call graph for fixture TS repo.

### P5.5 C/C++ Backend

Build:

- `compile_commands.py` parser.
- `libclang_adapter.py`.
- `clangd_adapter.py` using shared LSP client.
- `cmake_backend.py`.
- `ctest_detection.py`.
- `abi_edge_builder.py`.
- `cpp_backend.py` orchestrator.

Deliverables:

- `indexing/backends/cpp/`
- C/C++ fixture repository with `compile_commands.json`.
- C/C++ backend tests.

Acceptance:

- libclang produces symbols and includes for fixture C/C++ repo.

### P5.6 Optional Java Backend Stub

Build:

- `capability.py` with `JAVA_BACKEND_ENABLED` flag.
- `java_backend.py` stub with availability check.
- `jdt_adapter.py` minimal implementation.

Deliverables:

- `indexing/backends/java/`
- Java capability tests.

Acceptance:

- Flag defaults to False.
- Java fixture produces class/method nodes when enabled and JDK present.

### P5.7 Cross-Backend Fact Reconciliation

Build:

- `CrossChecker` evidence agreement model.
- `FactReconciler` merge logic.
- Reconciliation diagnostics.

Deliverables:

- `indexing/backends/cross_check.py`
- `indexing/backends/fact_reconciler.py`
- Cross-check and reconciliation tests.

Acceptance:

- Confirmed, candidate, and conflicting agreement states are exercised by fixture tests.

### P5.8 Build And Test Evidence Extension

Build:

- JavaScript/TypeScript build evidence detectors.
- C/C++ build evidence detectors.
- Extended Phase 3 build evidence integration.

Deliverables:

- `indexing/backends/typescript/ts_test_detection.py`
- `indexing/backends/cpp/ctest_detection.py`
- Extended build evidence tests.

Acceptance:

- jest, vitest, CTest, and CMake targets are detected in fixtures.

### P5.9 Incremental Update Integration

Build:

- Incremental hooks per backend.
- Snapshot invalidation for changed files.
- Summary cache invalidation integration.

Deliverables:

- Incremental support flags per backend.
- Incremental update tests for Python and C/C++.

Acceptance:

- Incremental update for Python file change produces correct supersession and summary invalidation.

### P5.10 Fixture Repositories And Regression Harness

Build:

- Extend Phase 3 Python fixture.
- TypeScript fixture repo.
- C/C++ fixture repo with `compile_commands.json`.
- Mixed-language fixture stub.
- Backend capability snapshot tests.
- Backend output schema validation tests.
- Diagnostic code coverage tests.

Deliverables:

- `tests/indexing/backends/fixtures/`
- Regression snapshot fixtures.
- Fixture README files.

Acceptance:

- All fixture-based integration tests pass.
- Capability snapshots are stable.

---

## 20. Suggested Implementation Order

Recommended order:

1. Backend base interface and capability model.
2. Backend registry.
3. LSP abstraction layer.
4. Python pyan3 adapter using shared LSP client foundations.
5. Python Pyright adapter.
6. Python backend orchestrator.
7. Cross-check and fact reconciler with Python fixture.
8. TypeScript Node.js runner script and tsmorph adapter.
9. madge adapter and package metadata.
10. TypeScript backend orchestrator with fixture.
11. Compile-commands parser.
12. libclang adapter.
13. clangd adapter using shared LSP client.
14. CMake File API and CTest.
15. C/C++ backend orchestrator with fixture.
16. Java backend stub and capability flag.
17. Build and test evidence extension.
18. Incremental update hooks.
19. Regression harness and snapshots.

Reasoning:

- LSP abstraction lands before Pyright and clangd to avoid duplication.
- Python backend hardening comes first because the Phase 3 Python fixture is already available.
- TypeScript before C/C++ because ts-morph is a pure Node.js dependency with fewer system requirements.
- C/C++ after TypeScript because it requires system-level libclang and `compile_commands.json` infrastructure.
- Java stub last because it is off by default and lowest priority for initial Phase 5 acceptance.

---

## 21. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 5 |
|---|---|
| Phase 6 - SARIF/static analysis | C/C++ and TypeScript graph nodes for alert binding; `warned_by` edges from Pyright and clangd diagnostics |
| Phase 7 - Interface plugins | C/C++ symbol and include graph for omniORB-IDL plugin; TypeScript symbol graph for HTTP-REST and WebSocket plugins |
| Phase 8 - Repo-QA | Multi-language symbol lookup; cross-language file-location answers |
| Phase 9 - Fault localisation | Expanded graph neighbor traversal for Python, TS, and C/C++ suspects |
| Phase 10 - Evaluation harness | JS/TS and C/C++ fixture repos for T2/T3 benchmark tracks |
| Phase 11 - Patch review | Multi-language changed-symbol detection; ABI edge annotations for C/C++ compatibility checks |
| Phase 12 - SAST repair | Pyright and clangd diagnostic nodes as repair targets |
| Phase 13 - Bug-resolve | Full multi-language graph traversal for investigation |
| Phase 15 - Blast radius | ABI edges and build targets from C/C++ for impact analysis |
| Phase 18 - Release gates | SWE-PolyBench-style and Defects4C-style calibration fixtures |

---

## 22. Exit Criteria Mapping

Source Phase 5 exit criterion:

- Python, JS/TS, and C/C++ repositories produce symbols and imports.

Concrete acceptance:

- Fixture Python repo: `graph_build` produces file, class, function, method, and import nodes with provenance.
- Fixture TypeScript repo: `graph_build` produces file, class, function, and import nodes with provenance.
- Fixture C/C++ repo: `graph_build` produces file, class, function, and include nodes with provenance.

Source Phase 5 exit criterion:

- At least one call-graph backend works per target language where tooling is available.

Concrete acceptance:

- Python: pyan3 `calls` edges present in fixture graph.
- TypeScript: ts-morph `calls` edges present in fixture graph.
- C/C++: libclang `calls` edges present in fixture graph.

Source Phase 5 exit criterion:

- Optional Java support has an explicit capability flag and can be exercised by Java calibration fixtures when enabled.

Concrete acceptance:

- `JAVA_BACKEND_ENABLED=False` by default.
- With flag enabled and JDK present, Java fixture produces class and method nodes.
- Java backend disabled does not affect other backends.

Source Phase 5 exit criterion:

- Backend errors are captured as index diagnostics.

Concrete acceptance:

- Missing tool produces `BACKEND_UNAVAILABLE` diagnostic, not crash.
- Single-file parse failure produces `FILE_PARSE_ERROR` diagnostic.
- LSP server crash produces `LSP_CRASH` diagnostic and failed session.
- C/C++ missing `compile_commands.json` produces `COMPILE_COMMANDS_MISSING` diagnostic.
- All diagnostics round-trip through Phase 1 diagnostic schema.

---

## 23. Definition Of Done

Phase 5 is done when:

- The backend base interface and capability model are implemented and tested.
- The LSP abstraction layer is implemented and tested with a mock server.
- The Python backend produces pyan3 call edges and Pyright diagnostic nodes for the Python fixture repo.
- The TypeScript backend produces symbol, import, and call edges for the TypeScript fixture repo.
- The C/C++ backend produces symbol, include, and call edges for the C/C++ fixture repo with `compile_commands.json`.
- The Java backend stub exists with capability flag defaulting to False.
- The cross-backend fact reconciler produces `confirmed`, `candidate`, and `conflicting` agreements for the Python fixture.
- Build and test evidence detection covers JavaScript/TypeScript and C/C++ build systems.
- Incremental update integration invalidates summary cache entries for changed files in at least Python and C/C++.
- All backend availability checks are fast and do not run analysis.
- All backend degradation scenarios produce typed diagnostics without crashing.
- Backend capability descriptor snapshots are stable.
- Fixture repositories for Python, TypeScript, and C/C++ are committed with README files.
- Phase 4 MCP `graph_build` and `graph_update` tasks continue to work with expanded backends.
- All Phase 3 Python indexing tests continue to pass.

---

## 24. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| libclang not installed on developer machines | C/C++ backend unavailable, blocking C/C++ fixture tests | Gate C/C++ integration tests on libclang availability check; document install steps; keep ctags baseline always active |
| ts-morph or Node.js not available | TypeScript backend unavailable | Gate TS integration tests on Node.js availability check; ctags/tree-sitter baseline always runs |
| pyan3 produces incorrect call edges for complex Python patterns | False `calls` edges pollute the graph | Mark pyan3 edges as `candidate` until cross-checked; emit conflicts rather than overwriting AST facts |
| LSP server hangs during fixture tests | CI timeout | Per-request timeout in `RequestDispatcher`; LSP lifecycle manager hard-kills after grace period |
| Runner scripts for ts-morph are modified and break adapter | Silent schema mismatch | Snapshot test for runner script output; version the runner script contract |
| C/C++ `compile_commands.json` gets out of sync with fixture | Fixture-based tests silently use stale compilation flags | CI step to check fixture `compile_commands.json` matches the fixture `CMakeLists.txt`; lint step |
| Cross-checker produces too many `conflicting` edges for noisy tools | Downstream consumers overwhelmed | Set minimum agreement threshold; allow per-backend noise floor configuration; emit conflicts as diagnostic bucket, not individual graph entries for high-volume mismatches |
| Phase 3 Python indexing performance regresses after refactoring | Build time increases for CI | Run Phase 3 Python fixture as a performance baseline test; track wall-time per backend in `BackendRunStats` |
| Java backend enabled by mistake in CI | Java-dependent tests fail on machines without JDK | Explicit environment variable required; default config does not enable Java; CI matrix excludes Java track unless explicitly requested |
| Multiple backend versions installed | Capability reports become unstable | Pin backend tool versions in `pyproject.toml` optional dependency groups; record version in `BackendAvailability` |

---

## 25. Completion Report Template

When Phase 5 implementation is complete, report:

```text
Phase 5 completion report

Implemented:
- Backend base interface and capability model:
- Backend registry:
- LSP abstraction layer:
- Python pyan3 adapter:
- Python Pyright adapter:
- TypeScript ts-morph adapter:
- TypeScript madge adapter:
- TypeScript package metadata and test detection:
- C/C++ libclang adapter:
- C/C++ clangd adapter:
- C/C++ CMake File API and CTest:
- Java backend stub (capability flag):
- Cross-backend fact reconciler:
- Build evidence extension (JS/TS and C/C++):
- Incremental update integration:

Verification:
- Python fixture graph build with pyan3 and Pyright:
- TypeScript fixture graph build with ts-morph:
- C/C++ fixture graph build with libclang:
- LSP abstraction layer tests:
- Cross-check reconciliation tests:
- Backend capability snapshot tests:
- Degradation scenario tests:
- Local verify command:

Exit criteria:
- Python, JS/TS, and C/C++ produce symbols and imports:
- At least one call graph backend per language:
- Java backend capability flag defaults to False:
- Backend errors produce typed diagnostics:
- Phase 3 Python tests still pass:

Known limitations:
-

Follow-up for Phase 6 (SARIF):
-
```

---

## 26. Minimal First Slice Within Phase 5

If Phase 5 needs to be split further, implement this first:

1. Backend base interface, `BackendOutput` model, and capability model.
2. Backend registry.
3. LSP abstraction layer with mock-server tests.
4. Python `pyan3` adapter.
5. Python backend orchestrator that combines Phase 3 AST + pyan3.
6. Cross-check and fact reconciler for Python fixture.
7. Updated Python fixture with cross-module calls.
8. Capability descriptor snapshot tests for Python backend.

This minimal slice hardens the Python backend, introduces the LSP infrastructure that TypeScript and C/C++ will share, and exercises the cross-check path before multi-language complexity is added. TypeScript and C/C++ backends can follow in subsequent slices once the backend base is proven.
