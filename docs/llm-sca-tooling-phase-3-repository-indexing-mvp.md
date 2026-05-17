# LLM-SCA Tooling Phase 3 Implementation Plan: Repository Indexing MVP

> Date: 2026-05-09
> Repository name: `evidence-sca`
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 3 - Repository Indexing MVP
> Primary objective: build the first deterministic repository intelligence graph for registered repositories, starting with Python code, git metadata, build/test evidence, graph slices, symbol-summary cache plumbing, blame-chain evidence, and index freshness reporting.

---

## 1. Phase Summary

Phase 3 is the first phase where `evidence-sca` turns repository files into typed graph evidence. Phase 1 defined the schemas. Phase 2 persisted repositories, snapshots, graph facts, artefacts, and operational events. Phase 3 implements the deterministic indexing pipeline that populates those stores.

This phase should build a practical MVP rather than a perfect call graph. The goal is to produce useful, provenance-rich evidence for a small Python repository and to establish the update/invalidation mechanics that later language backends, SARIF binding, interface plugins, repo-QA, fault localisation, and workflows depend on.

The central rule for this phase is:

```text
Indexing may be incomplete, but it must never be silent.
Every skipped file, missing backend, stale snapshot, heuristic edge, cache invalidation,
and partial result must be visible as typed diagnostics or operational events.
```

Phase 3 should implement:

- `graph_build(repo_path)` as a full deterministic index build.
- `graph_update(repo_path)` as a changed-file incremental update.
- File tree scanning.
- Git metadata and snapshot capture.
- Git blame-chain collection.
- Universal ctags adapter.
- Tree-sitter adapter for basic syntax facts.
- Python import/symbol indexing MVP.
- Build/test evidence detection MVP.
- Lazy symbol-summary cache plumbing.
- Graph slice generation around files and symbols.
- Full graph manifest generation with chunk references.
- Operational run events for indexing.

### Architecture Coverage

Phase 3 covers:

- F1 - Repository intelligence graph.
- `graph_build`.
- `graph_update`.
- Backing data for:
  - `code-intelligence://repos`
  - `code-intelligence://graph/{repo}`
  - `code-intelligence://graph/slice/{repo}/{files}`
  - `code-intelligence://summary/{repo}/{symbol_path}`
  - `code-intelligence://blame/{repo}/{file_path}`
  - `code-intelligence://build-evidence/{repo}`

Phase 3 does not implement MCP resource routing. It prepares the persisted records that Phase 4 exposes.

### Inherited Paper Anchors

Use these anchors in Phase 3 issues, ADRs, implementation notes, and indexing reports:

- `arise`
- `locagent`
- `repograph`
- `codexgraph`
- `rig`
- `hafixagent`
- `swe-polybench`

Adjacent anchors that may be useful in design notes:

- `logiclens`
- `cosil`
- `repo-aware-kg`
- `reporepair`
- `specrover`

## Technology Stack

Libraries and tools active in Phase 3. All versions are minimum constraints; exact pins are in `uv.lock`. Run every command via `uv run`.

| Library / Tool | PyPI package | Version | Purpose in this phase |
|---|---|---|---|
| universal-ctags | — (system binary) | latest stable | Symbol discovery (functions, classes, methods) across all languages; JSON output via `--output-format=json` |
| tree-sitter | `tree-sitter` | >=0.22 | AST parsing via Python binding (not subprocess); run in thread pool executor for CPU-bound work |
| tree-sitter-python | `tree-sitter-python` | >=0.22 | Python grammar for Phase 3 tree-sitter adapter |
| pyan3 | `pyan3` | >=1.4 | Python call/import graph; Python API only (not subprocess); run in `loop.run_in_executor` |
| orjson | `orjson` | >=3.10 | Parsing ctags JSON output; graph export chunks; all performance-critical JSON I/O |
| ruamel.yaml | `ruamel.yaml` | >=0.18 | Reading CI config files (`.github/workflows/*.yml`) and YAML metadata; always `YAML(typ='safe')` for untrusted input |
| SQLModel | `sqlmodel` | >=0.0.21 | Graph node/edge persistence; async sessions via `AsyncSession` |
| aiosqlite | `aiosqlite` | >=0.20 | Async SQLite driver for dev/CI |
| NetworkX | `networkx` | >=3.3 | In-memory graph traversal for slice generation; loaded from SQLModel tables |
| Pydantic v2 | `pydantic` | >=2.0 | All graph node/edge/result models; `model_config = ConfigDict(extra="forbid")` on stable contracts |

**Async subprocess convention (critical).** All calls to `universal-ctags` and all `git` commands in async code paths must use `asyncio.create_subprocess_exec`. Never use `subprocess.run` in any `async def` function. CPU-bound Python library calls (`pyan3`, tree-sitter parsing) must be wrapped in `loop.run_in_executor`.

Pattern for subprocess call in an async path:

```python
proc = await asyncio.create_subprocess_exec(
    "ctags", "--output-format=json", "--fields=+nKSt", "--extras=+q", "-f", "-", *files,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
stdout, stderr = await proc.communicate()
```

Pattern for a CPU-bound library call in an async path:

```python
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, pyan_callgraph_fn, source_files)
```

**Backend degradation.** Missing backends (`universal-ctags` not installed, grammar package absent) must degrade to partial evidence with a diagnostic entry in the `IndexingResult`, not raise an unhandled exception.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 3 depends on:

- Phase 1 schema models:
  - graph nodes and edges
  - provenance
  - snapshots
  - source spans
  - artefact references
  - run records and run events
  - graph diagnostics
- Phase 2 storage:
  - repository registry
  - snapshot ledger
  - graph store
  - graph query primitives
  - operational store
  - artefact registry
  - graph export/import
- Phase 0 package basics:
  - configuration model
  - logging
  - CLI entrypoint or internal command runner
  - test runner

### Phase Outputs

Phase 3 should produce:

- Indexing service.
- File scanner.
- Ignore/filter policy.
- Git metadata collector.
- Snapshot capture.
- Git blame-chain collector.
- Ctags adapter.
- Tree-sitter adapter.
- Python AST/import/symbol backend.
- Build/test evidence detector.
- Symbol-summary cache store and invalidation hooks.
- Graph manifest/chunk generation.
- Graph slice generator using Phase 2 graph query primitives.
- Index diagnostics.
- Index operational events.
- Fixture repositories and integration tests.

### Non-Goals

Do not implement these in Phase 3:

- MCP server routing.
- MCP task API.
- Resource subscriptions or notifications.
- Multi-language production-grade backends.
- Full interprocedural call graph precision.
- SARIF parsing or static-analysis execution.
- Interface plugin indexing.
- Fault localisation ranking.
- Repo-QA.
- Patch generation.
- LLM-generated summaries as a default requirement.
- Dynamic tracing.
- Memory retrieval.
- Evaluation benchmark runners.

Phase 3 can define interfaces and storage records for later consumers, but it should keep the MVP deterministic.

---

## 3. Recommended File Layout

Assuming package name `evidence_sca`:

```text
src/evidence_sca/
  indexing/
    __init__.py
    service.py
    pipeline.py
    config.py
    scanner.py
    ignore.py
    git_metadata.py
    snapshots.py
    blame.py
    diagnostics.py
    manifests.py
    summaries.py
    build_evidence.py
    graph_slices.py
    hashing.py
    provenance.py
    result.py

    backends/
      __init__.py
      base.py
      ctags.py
      tree_sitter.py
      python_ast.py

  cli/
    indexing.py

tests/
  fixtures/
    repos/
      python_basic/
      python_dirty_update/
      python_imports/
      python_tests/
      mixed_snapshot/
  indexing/
    test_scanner.py
    test_git_metadata.py
    test_blame.py
    test_ctags_backend.py
    test_tree_sitter_backend.py
    test_python_ast_backend.py
    test_build_evidence.py
    test_graph_build.py
    test_graph_update.py
    test_graph_slices.py
    test_summary_cache.py
    test_graph_manifest.py
    test_indexing_events.py
```

If the repository uses `llm_sca_tooling` as the package name before renaming, keep the same module boundaries and later rename mechanically.

---

## 4. Indexing Design Principles

### 4.1 Deterministic Evidence First

Parser, git, build/test, and filesystem facts should be deterministic and strongly provenanced. Heuristic and low-confidence facts are allowed only when explicitly marked.

Examples:

- File existence from scanner: high-confidence parser/filesystem evidence.
- Python import edge from AST: high-confidence parser evidence.
- Test-to-symbol edge from naming heuristic: lower-confidence heuristic evidence.
- Symbol summary text: hybrid or soft evidence, never a parser fact.

### 4.2 Partial Indexes Are Valid But Visible

An index can be partial when:

- A backend is unavailable.
- A file is skipped.
- A file cannot be parsed.
- A tree-sitter grammar is unavailable.
- Git is unavailable.
- Blame fails on an untracked file.
- A generated or vendor directory is skipped.

Partial state must appear in:

- Snapshot status.
- Repository index status.
- Graph diagnostics.
- Run events.

### 4.3 Snapshot Provenance Is Mandatory

Every graph fact must be tied to:

- Repo ID.
- `git_sha` when available.
- `worktree_snapshot_id` for dirty worktrees.
- File path and span when applicable.
- Source backend and version.
- Confidence and derivation.

### 4.4 Large Graphs Are Manifests, Not Dumps

`code-intelligence://graph/{repo}` will later expose a graph manifest plus chunk references. Phase 3 should generate the manifest and chunks in the artefact registry. Bounded work should use graph slices.

### 4.5 LLM Summaries Are Cache Entries, Not Hard Facts

The symbol-summary cache is keyed and invalidated in Phase 3. The actual summary generator can remain a stub or deterministic placeholder unless an approved local LLM interface already exists.

Rules:

- Summary records are keyed by repo, symbol path, `git_sha`, and dirty worktree snapshot.
- Summary records are invalidated when the owning file changes.
- Summary evidence is low-confidence or hybrid.
- Summary text never replaces parser graph evidence.

---

## 5. Indexing Pipeline

### 5.1 Full Build Flow

Recommended `graph_build(repo_path)` flow:

1. Resolve or register repository.
2. Create indexing run record.
3. Capture harness condition for indexing environment.
4. Capture git metadata and snapshot.
5. Mark repository index status as `indexing`.
6. Scan files.
7. Apply ignore and skip policy.
8. Record file nodes and directory/package containment nodes.
9. Run ctags adapter where available.
10. Run tree-sitter adapter where available.
11. Run Python AST backend for Python files.
12. Detect build/test evidence.
13. Collect blame-chain metadata for indexed files.
14. Merge backend outputs into graph facts.
15. Validate graph facts against Phase 1 schema.
16. Write graph facts transactionally through Phase 2 graph store.
17. Generate graph manifest and chunks.
18. Invalidate stale symbol summaries.
19. Record graph diagnostics.
20. Mark snapshot and repo index status as `fresh`, `partial`, or `failed`.
21. Close indexing run with final status.

### 5.2 Incremental Update Flow

Recommended `graph_update(repo_path)` flow:

1. Resolve repository.
2. Create indexing update run record.
3. Capture current git/worktree snapshot.
4. Compare against latest indexed snapshot.
5. Detect changed, added, deleted, and renamed files.
6. If changes cannot be safely scoped, fall back to full build or mark partial.
7. Re-scan changed files.
8. Remove or supersede graph facts for changed files in old snapshot.
9. Re-run relevant backends for changed files.
10. Recompute affected directory, module, import, test, and summary records.
11. Invalidate symbol summaries for changed files.
12. Refresh blame metadata for changed files.
13. Preserve unaffected graph facts when snapshot compatibility permits.
14. Generate updated graph manifest and chunks.
15. Mark mixed/stale state when old and new facts are both visible.
16. Record update diagnostics and operational events.

### 5.3 Pipeline Result

Recommended result object:

```text
IndexingResult
  repo_id
  run_id
  snapshot_id
  status: fresh | partial | failed | stale | unknown
  files_scanned
  files_indexed
  files_skipped
  nodes_added
  edges_added
  diagnostics
  graph_manifest_id
  artifact_refs
  stale_summary_count
  backend_versions
  started_ts
  ended_ts
```

Rules:

- `failed` should preserve diagnostics and partial artefacts where safe.
- `partial` should be usable by graph queries but cannot silently support confident downstream verdicts.
- Result should be serializable for CLI output and operational records.

---

## 6. File Tree Scanner

### 6.1 Responsibilities

The scanner discovers candidate files and basic file evidence.

Responsibilities:

- Walk registered repository roots.
- Normalize repo-relative paths.
- Apply ignore policy.
- Detect directories, files, packages, and modules.
- Detect file language by extension and lightweight content checks.
- Compute file hashes.
- Detect generated, vendor, binary, hidden, and oversized files.
- Emit file and directory graph nodes.
- Emit `contains` edges.
- Emit scanner diagnostics.

### 6.2 Ignore Policy

Default skip directories:

- `.git`
- `.hg`
- `.svn`
- `.llm-sca`
- `.evidence-sca`
- `.venv`
- `venv`
- `env`
- `node_modules`
- `dist`
- `build`
- `.mypy_cache`
- `.pytest_cache`
- `.ruff_cache`
- `__pycache__`
- `.tox`
- `.nox`
- `.eggs`

Default skip files:

- Binary files.
- Files over configured max size.
- Lock files can be indexed as package metadata but not parsed as code.
- Generated files can be included as file nodes but marked generated and skipped for manual-edit recommendations later.

### 6.3 Scanner Config

Recommended fields:

```text
IndexingConfig
  include_globs
  exclude_globs
  max_file_size_bytes
  follow_symlinks
  include_hidden
  include_generated
  language_allowlist
  backend_timeout_ms
  graph_slice_limit
  manifest_chunk_size
```

Default behavior:

- Do not follow symlinks outside repo root.
- Do not index binary content.
- Include test files.
- Include docs/spec markdown as document nodes if small.
- Include package metadata files as build evidence candidates.

### 6.4 Scanner Graph Output

Node types:

- `repo`
- `directory`
- `file`
- `package`
- `module`
- `document`

Edges:

- `contains`
- `documents` only for obvious doc-to-file metadata if deterministic; otherwise defer.

Provenance:

- `source_tool=evidence-sca.scanner`
- `derivation=parser` or `heuristic` depending on fact.
- `evidence_strength=hard_static` for file existence and containment.

### 6.5 Scanner Tests

Required tests:

- Ignores `.git`, caches, virtualenvs, and build dirs.
- Detects Python files.
- Detects test files.
- Detects binary files and skips with diagnostic.
- Detects oversized files and skips with diagnostic.
- Produces repo-relative paths.
- Produces directory/file containment graph.
- Handles symlink policy safely.

---

## 7. Git Metadata Collector

### 7.1 Responsibilities

The git metadata collector captures repository state.

Responsibilities:

- Detect whether repo uses git.
- Capture current `git_sha`.
- Capture branch.
- Detect dirty worktree.
- Capture changed files.
- Capture untracked files.
- Compute worktree snapshot ID for dirty state.
- Detect latest indexed snapshot from Phase 2.
- Emit snapshot ledger records.
- Emit stale/dirty diagnostics.

### 7.2 Git Commands

Use deterministic git commands:

```text
git rev-parse HEAD
git rev-parse --abbrev-ref HEAD
git status --porcelain=v1
git diff --name-only
git diff --cached --name-only
git ls-files --others --exclude-standard
```

Do not require network access.

### 7.3 Worktree Snapshot ID

Dirty snapshot ID should be stable for the observed dirty state.

Recommended hash inputs:

- Repo ID.
- Current `git_sha`.
- Changed file paths.
- File content hashes for changed tracked files.
- File content hashes for untracked indexed files.
- Indexing config hash.

Recommended format:

```text
snap:<repo-id>:dirty:<short-hash>
```

### 7.4 Snapshot Status Rules

Rules:

- Clean build over current HEAD can mark snapshot `fresh`.
- Dirty build can mark snapshot `fresh` for that worktree snapshot, but repository status should expose dirty state.
- If current worktree differs from latest indexed snapshot, repo status becomes `stale`.
- If a backend fails for some files, snapshot status is `partial`.
- If graph query combines old and new facts, query status is `mixed`.

### 7.5 Git Metadata Tests

Required tests:

- Clean git repo snapshot.
- Dirty tracked file snapshot.
- Staged change snapshot.
- Untracked file snapshot.
- Non-git repo fallback.
- Changed-file detection.
- Stable worktree snapshot ID for unchanged dirty state.
- New snapshot ID when dirty file content changes.

---

## 8. Git Blame-Chain Collector

### 8.1 Purpose

The blame-chain collector produces backing data for `code-intelligence://blame/{repo}/{file_path}` and supports later fault localisation and operational evidence.

### 8.2 Responsibilities

Responsibilities:

- Collect blame metadata for indexed text files.
- Preserve commit, author timestamp, line range, and summary where available.
- Collect parent commit chain for a file where practical.
- Store blame records as artefacts or graph evidence.
- Record diagnostics when blame is unavailable.
- Handle untracked and dirty files explicitly.

### 8.3 Recommended Commands

Use:

```text
git blame --line-porcelain -- <file>
git log --follow --format=... -- <file>
```

Rules:

- Do not run blame on binary files.
- Do not treat blame output as proof of semantic ownership.
- Dirty/uncommitted lines should be marked as current worktree evidence.

### 8.4 Blame Data Model

Recommended record:

```text
BlameChain
  blame_id
  repo_id
  snapshot_id
  file_path
  git_sha
  worktree_snapshot_id
  line_entries
  commit_chain
  artifact_ref
  diagnostics
  provenance
```

Recommended line entry:

```text
BlameLine
  line_no
  commit_sha
  author_time
  summary
  original_file_path
  original_line_no
```

### 8.5 Storage Choice

Phase 3 can store blame chains as:

- Artefact payloads referenced by graph/file metadata.
- Operational/indexing artefacts.
- Optional graph nodes for commit/file evidence if Phase 1 models are ready.

The critical requirement is that blame chains can be cached, invalidated, and retrieved with snapshot provenance.

### 8.6 Blame Tests

Required tests:

- Blame for committed file.
- Blame chain after file modification.
- Blame unavailable for untracked file produces diagnostic.
- Blame cache invalidates when file changes.
- Blame output links to repo, snapshot, file path, and artefact hash.

---

## 9. Backend Interface

### 9.1 Backend Contract

Define a common backend interface so ctags, tree-sitter, and Python AST can emit the same graph schema.

Recommended protocol:

```text
IndexBackend
  backend_id
  backend_version()
  supported_languages()
  detect_capabilities(repo, files) -> BackendCapabilities
  index_files(context, files) -> BackendResult
```

Recommended `BackendResult`:

```text
BackendResult
  backend_id
  backend_version
  nodes
  edges
  diagnostics
  artifact_refs
  files_processed
  files_skipped
  started_ts
  ended_ts
```

### 9.2 Backend Rules

Rules:

- Backends emit Phase 1 graph models only.
- Backends must include provenance on every node and edge.
- Backend failures should not crash the entire build unless the backend is required by config.
- Backend output must be validated before store writes.
- Different backends can emit overlapping facts; merge policy decides deduplication.

### 9.3 Capability Reporting

Capability fields:

- Backend installed.
- Version.
- Supported languages.
- Supported node types.
- Supported edge types.
- Requires external binary.
- Timeout behavior.
- Known limitations.

Capability reporting feeds:

- Index diagnostics.
- Harness metadata.
- Operational events.
- Later MCP resource status.

---

## 10. Universal Ctags Adapter

### 10.1 Purpose

Ctags provides broad symbol discovery with low implementation complexity.

### 10.2 Responsibilities

Responsibilities:

- Detect `ctags` or `universal-ctags`.
- Record backend version.
- Run ctags on supported files.
- Parse JSON output when available.
- Emit symbol nodes.
- Emit containment edges from file/module to symbols.
- Preserve spans and signatures where available.
- Record unsupported language or parse diagnostics.

### 10.3 Recommended Command

Prefer JSON output:

```text
ctags --output-format=json --fields=+nKSt --extras=+q -f - <files...>
```

If JSON output is unavailable:

- Skip ctags backend with diagnostic.
- Do not parse legacy tags format unless explicitly implemented and tested.

### 10.4 Ctags Graph Output

Node types:

- `class`
- `function`
- `method`
- `variable`
- `type`
- `module`

Edges:

- `contains`

Confidence:

- High for symbol existence when ctags returns line data.
- Lower for ambiguous or missing span facts.

### 10.5 Ctags Tests

Required tests:

- Adapter detects missing ctags and records diagnostic.
- Adapter parses ctags JSON fixture.
- Python functions/classes become graph nodes.
- File-to-symbol containment edges are emitted.
- Backend version is recorded.
- Invalid ctags JSON fails gracefully.

---

## 11. Tree-Sitter Adapter

### 11.1 Purpose

Tree-sitter provides syntax-level evidence with consistent spans across languages.

### 11.2 Phase 3 Scope

Phase 3 only needs basic syntax facts:

- Module/file node enrichment.
- Class/function/method declarations.
- Import statement locations.
- Basic call-expression candidates where trivial.

Do not attempt a full semantic call graph in Phase 3.

### 11.3 Responsibilities

Responsibilities:

- Detect installed tree-sitter library and grammars.
- Parse Python files initially.
- Emit symbol declaration nodes.
- Emit import candidate nodes or edges where deterministic.
- Emit syntax diagnostics for parse errors.
- Preserve byte and line spans.

### 11.4 Tree-Sitter Graph Output

Node types:

- `module`
- `class`
- `function`
- `method`
- `variable` where simple assignment is clear

Edges:

- `contains`
- `imports` only when target module string is deterministic
- `calls` only for local syntactic call candidates marked as lower confidence if unresolved

### 11.5 Tree-Sitter Tests

Required tests:

- Parses simple Python module.
- Extracts functions and classes with spans.
- Emits import locations.
- Handles syntax error with diagnostic and partial output.
- Records grammar version or package version.
- Does not mark unresolved call candidates as hard semantic facts.

---

## 12. Python Import/Symbol Indexing MVP

### 12.1 Purpose

The Python backend should provide the first useful deterministic graph for real repositories.

### 12.2 Implementation Recommendation

Use Python's standard `ast` module for the MVP. It is deterministic, available by default, and enough for:

- Module nodes.
- Class/function/method nodes.
- Import edges.
- Basic containment.
- Decorator metadata.
- Test function detection.
- Simple call candidates.

Tree-sitter can enrich syntax spans but should not be required for the MVP.

### 12.3 Python Graph Facts

Node types:

- `module`
- `class`
- `function`
- `method`
- `variable`
- `test`

Edges:

- `contains`
- `imports`
- `calls` for same-module resolvable calls only in MVP
- `tests` for deterministic or heuristic test associations

### 12.4 Module Resolution

Phase 3 should implement basic import resolution:

- Absolute imports within repo packages.
- Relative imports within packages.
- `from x import y`.
- `import x as alias`.
- `from . import y`.

Do not require full Python packaging semantics yet.

Resolution result types:

- `resolved_internal`
- `external_dependency`
- `unresolved`
- `ambiguous`

Rules:

- Internal resolved imports can create `imports` edges with high confidence.
- External dependencies can become package/dependency metadata but not internal graph edges unless represented as external nodes by policy.
- Unresolved imports create diagnostics or low-confidence candidates.
- Ambiguous imports must not become hard edges.

### 12.5 Qualified Names

Recommended qualified name format:

```text
package.module:ClassName.method_name
package.module:function_name
```

Rules:

- Qualified names should be deterministic.
- Nested functions and classes should include containing scope.
- Generated stable node IDs should use repo ID, snapshot ID or file hash, qualified name, span, and node type.

### 12.6 Test Detection

Detect:

- Files under `tests/`.
- Files named `test_*.py` or `*_test.py`.
- Functions named `test_*`.
- Classes named `Test*`.
- Pytest fixtures via `@pytest.fixture`.

Edges:

- `contains` from test file/module to test functions.
- `tests` from test nodes to target symbols only when deterministic or a clearly marked heuristic exists.

Heuristic examples:

- `test_parse_config` may target `parse_config` when same repo has a unique symbol.
- Test file `test_config.py` may target `config.py` with lower confidence.

### 12.7 Call Detection Scope

MVP call detection should be conservative.

Allowed high-confidence calls:

- `foo()` to same-module function `foo`.
- `self.method()` to method in same class when resolvable.
- `ClassName.method(self)` or direct class method references where clear.

Lower-confidence candidates:

- Imported alias calls.
- Attribute chains.
- Dynamic dispatch.

Do not emit high-confidence `calls` edges for dynamic, unresolved, or ambiguous calls.

### 12.8 Python Backend Tests

Required tests:

- Module node creation.
- Function/class/method node creation.
- Nested symbols produce stable qualified names.
- Absolute internal import resolves.
- Relative import resolves.
- External import is marked external/unresolved without failing.
- Syntax error file produces diagnostic.
- Pytest tests are detected.
- Simple same-module call edge is emitted.
- Dynamic call does not become high-confidence hard fact.

---

## 13. Build/Test Evidence Detector MVP

### 13.1 Purpose

Build/test evidence should become graph evidence early because later workflows need to know which checks exist before they trust patch or implementation verdicts.

### 13.2 Scope

Phase 3 detects evidence. It does not run tests.

Detect:

- Pytest availability from files/config.
- Python package manager files.
- Common test directories.
- CI workflow files.
- Build configuration files.

### 13.3 Files To Detect

Python/package metadata:

- `pyproject.toml`
- `setup.py`
- `setup.cfg`
- `requirements.txt`
- `requirements-dev.txt`
- `Pipfile`
- `poetry.lock`
- `uv.lock`
- `tox.ini`
- `noxfile.py`

Test evidence:

- `tests/`
- `test/`
- `*_test.py`
- `test_*.py`
- `pytest.ini`
- `conftest.py`

CI evidence:

- `.github/workflows/*.yml`
- `.github/workflows/*.yaml`
- `.gitlab-ci.yml`
- `azure-pipelines.yml`

### 13.4 Graph Output

Node types:

- `build_target`
- `test`
- `ci_job`
- `file`

Edges:

- `contains`
- `tests`
- `documents` only where config deterministically documents test/build behavior.

Provenance:

- `derivation=build` for build/test metadata.
- `evidence_strength=structured_repository` or `hard_static` depending on fact.

### 13.5 Build/Test Evidence Tests

Required tests:

- Detects pytest config in `pyproject.toml`.
- Detects `tests/` directory.
- Detects test functions from Python backend.
- Detects GitHub Actions workflow file.
- Emits build/test evidence nodes.
- Does not claim tests were run.
- Records diagnostics for unsupported config parse.

---

## 14. Symbol-Summary Cache

### 14.1 Purpose

The summary cache backs `code-intelligence://summary/{repo}/{symbol_path}` in Phase 4 and later LLM workflows. Phase 3 should implement cache keys, storage, retrieval, and invalidation. Summary generation can be a stub.

### 14.2 Cache Key

Recommended key fields:

- Repo ID.
- Symbol path or node ID.
- File path.
- Git SHA.
- Worktree snapshot ID.
- Symbol span hash.
- Summary generator ID.
- Summary policy hash.

### 14.3 Summary Record

Recommended record:

```text
SymbolSummaryRecord
  summary_id
  repo_id
  snapshot_id
  symbol_node_id
  symbol_path
  file_path
  span
  summary_text
  confidence
  derivation
  generator_id
  source_artifact_refs
  created_ts
  invalidated_ts
  invalidation_reason
  provenance
```

### 14.4 Storage

The summary cache can use:

- A dedicated table in Phase 3 migration if preferred.
- The artefact registry plus graph node metadata.
- A small JSON store under `.evidence-sca/summaries/`.

Recommended for Phase 3:

- Add a `symbol_summaries` table or storage module if Phase 2 store is easy to extend.
- Otherwise store as artefacts with a clear typed metadata payload.

### 14.5 Invalidation Rules

Invalidate a summary when:

- Owning file hash changes.
- Symbol span changes.
- Symbol node ID changes.
- Snapshot changes and dirty state differs.
- Summary generator version or policy changes.

Rules:

- Invalidated summaries remain auditable but are not returned as current.
- Summary cache misses should not block graph indexing.
- Summary records must not be treated as parser facts.

### 14.6 Summary Tests

Required tests:

- Cache key includes snapshot identity.
- Cache hit for unchanged symbol.
- Cache miss after file hash changes.
- Dirty worktree snapshot gets separate summary key.
- Invalidated summary is not returned as current.
- Summary provenance marks hybrid or soft evidence.

---

## 15. Graph Merge And Deduplication

### 15.1 Purpose

Multiple backends may emit overlapping facts. Merge logic should avoid duplicate nodes and preserve provenance.

### 15.2 Node Deduplication

Recommended stable identity fields:

- Repo ID.
- Snapshot ID.
- Node type.
- File path.
- Qualified name.
- Span.

Rules:

- Exact duplicate facts can merge provenance sources.
- Conflicting facts should both be retained only if they represent distinct evidence, with diagnostics.
- Higher-confidence parser facts can supersede lower-confidence heuristic facts for canonical lookup, but lower-confidence facts should remain traceable if useful.

### 15.3 Edge Deduplication

Recommended stable identity fields:

- Repo ID.
- Snapshot ID.
- Edge type.
- Source ID.
- Target ID.
- Provenance class.

Rules:

- Same edge from multiple deterministic backends can merge provenance.
- LLM or heuristic edge should not overwrite parser/analyser edge.
- Ambiguous candidate edges should remain low-confidence and clearly marked.

### 15.4 Merge Diagnostics

Diagnostics:

- Duplicate node merged.
- Conflicting symbol span.
- Conflicting import resolution.
- Backend disagreement.
- Heuristic downgraded.
- Ambiguous edge retained as candidate.

### 15.5 Merge Tests

Required tests:

- Ctags and Python AST duplicate function node merge.
- Conflicting spans create diagnostic.
- Parser import edge outranks heuristic edge.
- Heuristic edge remains low-confidence.
- Duplicate edge insert is idempotent when payload hash matches.

---

## 16. Graph Manifest And Chunk Generation

### 16.1 Purpose

Full graph resources must be manifests with chunk references. Phase 3 should generate those records after build/update.

### 16.2 Manifest Content

Recommended manifest fields:

- Graph ID.
- Repo ID.
- Snapshot ID.
- Schema version.
- Node count.
- Edge count.
- Node type counts.
- Edge type counts.
- Chunk artefact IDs.
- Diagnostics summary.
- Generated timestamp.
- Indexing run ID.
- Backend versions.
- Snapshot consistency.

### 16.3 Chunking Strategy

Recommended chunk types:

- Nodes by type.
- Edges by type.
- Diagnostics.
- Optional file-level chunks for future partial loading.

Rules:

- Chunk payloads must include schema version.
- Chunks must be content-hashed.
- Manifest references chunks by artefact ID and hash.
- Full graph reads should go through manifest/chunks.

### 16.4 Manifest Tests

Required tests:

- Manifest generated for small graph.
- Chunk artefacts are stored.
- Node and edge counts match store query counts.
- Hash verification passes.
- Manifest references indexing run ID and snapshot ID.

---

## 17. Graph Slice Generation

### 17.1 Purpose

Graph slices are the bounded context unit for later MCP tools and LLM workflows.

### 17.2 Slice Inputs

Supported MVP slice requests:

- Files.
- Symbol node IDs.
- Qualified symbol paths.
- Depth.
- Edge type filters.
- Node type filters.
- Limit.

### 17.3 Slice Behavior

Rules:

- Use Phase 2 graph query primitives.
- Include files, symbols, imports, tests, and provenance.
- Include snapshot consistency metadata.
- Include diagnostics and truncation.
- Return `unknown` or diagnostic state for stale/mixed evidence rather than hiding it.

### 17.4 Default Expansion

For file slice:

1. Include file node.
2. Include contained module/symbol nodes.
3. Include import neighbours.
4. Include test nodes linked by deterministic or heuristic evidence.
5. Include parent package/directory nodes.

For symbol slice:

1. Include symbol node.
2. Include containing file/module/class.
3. Include imports in owning module.
4. Include same-depth callers/callees where available.
5. Include tests linked to symbol.

### 17.5 Slice Tests

Required tests:

- File slice includes file, module, symbols, imports, tests, and provenance.
- Symbol slice includes containing file/module and neighbours.
- Slice detects mixed snapshots.
- Slice truncation is explicit.
- Slice output validates against Phase 1 graph document or slice model.

---

## 18. Incremental Update And Invalidation

### 18.1 Changed File Detection

Use git metadata where available:

- Modified.
- Added.
- Deleted.
- Renamed.
- Staged.
- Untracked.

For non-git repos:

- Compare file hashes against latest indexed file records.

### 18.2 Update Scope

For changed files:

- Re-scan file metadata.
- Re-run language backends for changed files.
- Delete or supersede old nodes/edges for changed files.
- Recompute imports touching changed modules.
- Refresh blame for changed files.
- Invalidate summaries for changed symbols.

### 18.3 Affected Downstream Records

Phase 3 should define invalidation hooks for later phases:

- Symbol summaries.
- SARIF bindings.
- Blame metadata.
- Cross-language/interface links.
- Build/test evidence.

If the relevant backend is not implemented yet, record a placeholder diagnostic or invalidation event.

### 18.4 Deletions And Renames

Rules:

- Deleted files should mark prior facts stale or superseded for the new snapshot.
- Renamed files should preserve history where git reports rename, but not silently reuse node IDs if path/qualified names changed.
- Graph queries over latest snapshot should not return deleted current files unless historical mode is explicit.

### 18.5 Incremental Update Tests

Required tests:

- Modify Python file updates function span/hash.
- Add Python file creates new file/module/symbol nodes.
- Delete Python file removes or supersedes current graph facts.
- Rename file records diagnostic and updated graph facts.
- Summary cache invalidates for changed file.
- Unaffected file facts remain queryable.
- Update falls back to full rebuild when scope cannot be determined.

---

## 19. Operational Events For Indexing

### 19.1 Required Events

Graph build/update runs should produce operational events for:

- Run start.
- Harness condition recorded.
- Snapshot captured.
- Files scanned.
- Files skipped and reasons.
- Backend started.
- Backend completed.
- Backend failed.
- Backend versions.
- Nodes/edges written.
- Graph diagnostics.
- Blame collected.
- Summary cache invalidated.
- Graph manifest generated.
- Stale or dirty snapshot warning.
- Final index status.
- Run closed.

### 19.2 Event Payloads

Recommended payload summaries:

- Counts, not large raw data.
- Artefact IDs for large backend output.
- Diagnostics IDs.
- Backend ID and version.
- Repo ID and snapshot ID.
- Redaction status.

### 19.3 Harness Condition For Indexing

Record:

- `evidence-sca` version.
- Python runtime version.
- Storage schema version.
- Active indexing config hash.
- Backend versions.
- Permission profile.
- Sandbox/network policy.
- Verification gates if run inside a workflow.
- Telemetry/redaction policy.

### 19.4 Event Tests

Required tests:

- Full build creates run record.
- Full build records snapshot event.
- Backend version event is recorded.
- Skipped file event is recorded.
- Failed backend records diagnostic and event.
- Final run status matches indexing result.
- Dirty snapshot warning event is recorded for dirty repo.

---

## 20. CLI Or Internal Entrypoints

Phase 3 can expose internal commands or CLI subcommands, depending on Phase 0.

Recommended commands:

```text
evidence-sca graph build <repo-path>
evidence-sca graph update <repo-path>
evidence-sca graph status <repo-id-or-path>
evidence-sca graph slice <repo-id-or-path> --file <path>
```

If CLI is not ready, implement service methods:

```text
graph_build(repo_path, *, config=None) -> IndexingResult
graph_update(repo_path, *, config=None, snapshot=None) -> IndexingResult
get_graph_slice(repo, files=None, symbols=None, depth=1) -> GraphSlice
```

Rules:

- CLI output should be concise.
- Detailed data should be persisted and referenced by run ID.
- Commands should avoid network.
- Commands should not execute tests or package installs in this phase.

---

## 21. Error Handling And Diagnostics

### 21.1 Error Types

Recommended exceptions:

- `IndexingError`
- `RepositoryResolutionError`
- `SnapshotCaptureError`
- `FileScanError`
- `BackendUnavailableError`
- `BackendExecutionError`
- `BackendParseError`
- `GraphMergeError`
- `GraphWriteError`
- `BlameCollectionError`
- `SummaryCacheError`
- `ManifestGenerationError`

### 21.2 Diagnostic Severity

Use:

- `info`
- `warning`
- `error`

Rules:

- Backend unavailable is warning when backend is optional.
- Backend unavailable is error when configured as required.
- File parse failure is warning for one file, error only if policy says all files must parse.
- Graph write failure is error.
- Snapshot capture failure is error unless non-git fallback is allowed.

### 21.3 Partial Failure Policy

Rules:

- One parse failure should not fail full indexing.
- Store write failure should fail the build transaction.
- Missing optional backend should produce partial diagnostics.
- Missing git should allow non-git indexing with `unknown` or content-hash snapshot.
- Blame failure should not fail graph build.

---

## 22. Security And Privacy

### 22.1 Path Safety

Rules:

- All indexed file paths are repo-relative.
- Symlinks outside repo root are skipped by default.
- Exported graph manifests do not expose absolute local paths.
- Path normalization must prevent `..` escape in file IDs or artefact paths.

### 22.2 Content Handling

Rules:

- Do not store full source file content in graph nodes.
- Store hashes, spans, and bounded snippets only when explicitly configured.
- Large backend outputs are artefacts with redaction status.
- Binary files are skipped by default.

### 22.3 Command Safety

Rules:

- Backend commands must be non-networked.
- Shell commands should use argument arrays, not shell strings, in implementation.
- Timeouts apply to external backends.
- Backend stderr should be redacted before persistence if it may contain paths or source snippets.

---

## 23. Performance Boundaries

Phase 3 should remain small but avoid obvious bottlenecks.

Recommended defaults:

- Max indexed file size: 1 MiB for source files.
- Max backend timeout per batch: configurable, default 30 seconds.
- Max graph slice nodes: inherited from Phase 2, default 2,000.
- Manifest chunk size: configurable, default 1,000 nodes or edges per chunk.
- Batch graph writes: at least per backend or per file group.

Rules:

- Do not read full file content more times than necessary.
- Hash files during scan and reuse hashes.
- Batch storage writes.
- Keep backend artefacts only when useful for diagnostics.
- Truncate diagnostics safely.

---

## 24. Fixture Repositories

Create small fixture repos that exercise core behavior.

### 24.1 `python_basic`

Contents:

- `src/pkg/__init__.py`
- `src/pkg/core.py`
- `src/pkg/helpers.py`
- `tests/test_core.py`
- `pyproject.toml`

Cases:

- Module nodes.
- Function/class nodes.
- Import edges.
- Test detection.
- Build/test evidence.

### 24.2 `python_dirty_update`

Contents:

- Git repo initialized in test setup.
- One committed Python file.
- Test modifies file during test.

Cases:

- Dirty snapshot.
- Incremental update.
- Summary invalidation.

### 24.3 `python_imports`

Contents:

- Relative imports.
- Absolute internal imports.
- External import.
- Ambiguous import case.

Cases:

- Import resolution confidence.
- Diagnostics for unresolved imports.

### 24.4 `python_tests`

Contents:

- Pytest functions.
- Pytest fixtures.
- Test class.
- `conftest.py`.

Cases:

- Test nodes.
- Heuristic `tests` edges.
- Build/test evidence.

### 24.5 `mixed_snapshot`

Contents:

- Graph facts across two snapshots inserted or created through update.

Cases:

- Mixed-snapshot slice detection.
- Stale index status.

---

## 25. Test Plan

### 25.1 Unit Tests

Required:

- File ignore policy.
- Language detection.
- File hashing.
- Path normalization.
- Worktree snapshot hash.
- Backend capability records.
- Python qualified name generation.
- Import resolution.
- Summary cache key.
- Diagnostic severity mapping.

### 25.2 Backend Tests

Required:

- Ctags available path with fixture JSON.
- Ctags missing path.
- Tree-sitter parse success.
- Tree-sitter parse error.
- Python AST parse success.
- Python AST syntax error.
- Python import resolution.
- Python call candidate confidence.

### 25.3 Integration Tests

Required:

- `graph_build` indexes `python_basic`.
- `graph_build` stores repo, snapshot, nodes, edges, diagnostics, manifest, and run events.
- `graph_update` updates changed files without rebuilding everything.
- Graph slice includes files, symbols, imports, tests, and provenance.
- Blame chain is cached and retrieved with snapshot provenance.
- Summary cache invalidates on file change.
- Stale index state is visible.
- Partial backend failure still closes run with partial status and diagnostics.

### 25.4 Store Interaction Tests

Required:

- Index build writes through Phase 2 graph store.
- Graph facts validate against Phase 1 models before write.
- Batch write rollback on invalid graph fact.
- Indexing run events are append-only.
- Graph manifest chunks are artefact records with hashes.

### 25.5 CLI Tests

If CLI exists:

- `graph build` returns run ID and status.
- `graph update` returns changed file counts.
- `graph status` reports stale/fresh/partial.
- `graph slice --file` returns bounded JSON.

---

## 26. Work Packages

### P3.1 Indexing Service And Config

Build:

- `IndexingConfig`.
- `IndexingContext`.
- `IndexingResult`.
- `IndexingService`.
- Full build and update method skeletons.

Deliverables:

- `indexing/config.py`
- `indexing/service.py`
- `indexing/result.py`
- Unit tests.

Acceptance:

- Service can resolve registered repo and create a structured indexing result.

### P3.2 File Scanner And Ignore Policy

Build:

- Repo walker.
- Ignore policy.
- File metadata capture.
- File/directory/package/module node emission.
- Containment edges.

Deliverables:

- `indexing/scanner.py`
- `indexing/ignore.py`
- Scanner tests.

Acceptance:

- Scanner emits typed graph facts and diagnostics for fixture repos.

### P3.3 Git Metadata And Snapshot Capture

Build:

- Git command adapter.
- Clean/dirty snapshot capture.
- Changed-file detection.
- Worktree snapshot ID.
- Snapshot ledger writes.

Deliverables:

- `indexing/git_metadata.py`
- `indexing/snapshots.py`
- Git metadata tests.

Acceptance:

- Clean and dirty snapshots are represented and stored.

### P3.4 Python AST Backend

Build:

- Python AST parser.
- Module, class, function, method nodes.
- Import resolution MVP.
- Test detection.
- Conservative call edges.

Deliverables:

- `indexing/backends/python_ast.py`
- Python backend tests.

Acceptance:

- Small Python repo produces symbols/imports/tests with provenance.

### P3.5 Ctags Backend

Build:

- Backend detection.
- Version capture.
- JSON output parser.
- Symbol node emission.
- Diagnostics for missing/unusable binary.

Deliverables:

- `indexing/backends/ctags.py`
- Ctags tests using fixture JSON.

Acceptance:

- Ctags can enrich symbol discovery when available without being required.

### P3.6 Tree-Sitter Backend

Build:

- Backend detection.
- Python grammar parse.
- Basic declaration extraction.
- Parse diagnostics.

Deliverables:

- `indexing/backends/tree_sitter.py`
- Tree-sitter tests.

Acceptance:

- Tree-sitter enriches syntax spans when available without being required.

### P3.7 Build/Test Evidence Detector

Build:

- Package metadata detection.
- Pytest config detection.
- Test directory and file detection.
- CI workflow detection.
- Build/test graph nodes.

Deliverables:

- `indexing/build_evidence.py`
- Build/test evidence tests.

Acceptance:

- `python_basic` fixture yields build/test evidence without running tests.

### P3.8 Blame-Chain Collector

Build:

- Git blame command wrapper.
- Git log follow wrapper.
- Blame chain model/artefact storage.
- Dirty/untracked file diagnostics.

Deliverables:

- `indexing/blame.py`
- Blame tests.

Acceptance:

- Blame chains can be cached, invalidated, and retrieved with snapshot provenance.

### P3.9 Graph Merge, Write, And Manifest Generation

Build:

- Backend result merge logic.
- Deduplication.
- Conflict diagnostics.
- Transactional graph writes.
- Graph manifest and chunk generation.

Deliverables:

- `indexing/pipeline.py`
- `indexing/manifests.py`
- Merge/manifest tests.

Acceptance:

- Full build writes validated graph facts and creates manifest chunks.

### P3.10 Summary Cache Plumbing

Build:

- Summary cache key.
- Summary record storage.
- Current summary lookup.
- Invalidation on file/symbol change.
- Stub generator interface.

Deliverables:

- `indexing/summaries.py`
- Summary cache tests.

Acceptance:

- Summary records are snapshot-keyed and invalidated correctly.

### P3.11 Graph Slice Generator

Build:

- File slice.
- Symbol slice.
- Default expansion.
- Snapshot/truncation diagnostics.

Deliverables:

- `indexing/graph_slices.py`
- Slice tests.

Acceptance:

- Slices include files, symbols, imports, tests, provenance, and snapshot metadata.

### P3.12 Operational Events For Indexing

Build:

- Indexing run lifecycle.
- Backend event emission.
- Diagnostic events.
- Final status events.

Deliverables:

- Event integration in `indexing/service.py`.
- Operational event tests.

Acceptance:

- Graph build/update runs produce reviewable operational records.

### P3.13 CLI Or Internal Entrypoints

Build:

- `graph build`.
- `graph update`.
- `graph status`.
- Optional `graph slice`.

Deliverables:

- `cli/indexing.py`.
- CLI tests if CLI exists.

Acceptance:

- Developer can run index build/update locally and get run ID/status.

---

## 27. Suggested Implementation Order

Recommended order:

1. Indexing config, context, result objects.
2. File scanner and ignore policy.
3. Git metadata and snapshot capture.
4. Basic graph write from scanner output.
5. Python AST backend.
6. Build/test evidence detector.
7. Graph merge and deduplication.
8. Graph manifest generation.
9. Graph slice generation.
10. Incremental update.
11. Summary cache invalidation.
12. Blame-chain collector.
13. Optional ctags adapter.
14. Optional tree-sitter adapter.
15. Operational event completeness.
16. CLI/internal commands.

Reasoning:

- Scanner plus snapshot capture creates the first useful deterministic graph.
- Python AST gives MVP symbol/import coverage without external binaries.
- Optional ctags/tree-sitter should enrich, not block, the MVP.
- Incremental update should be added after full build is stable.

---

## 28. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 3 |
|---|---|
| Phase 4 - MCP server core | Backing data for repo, graph, graph slice, summary, blame, and build-evidence resources |
| Phase 4A - Operational runtime plane | Indexing run records, backend events, diagnostics, stale/dirty snapshot warnings |
| Phase 5 - Language backend expansion | Backend interface, capability reporting, merge policy, diagnostics, multi-language extension points |
| Phase 6 - SARIF/static analysis | File/span graph nodes for alert binding, build/test evidence, snapshot-aware graph facts |
| Phase 7 - Interface plugins | File/symbol/module graph substrate and plugin reload invalidation hooks |
| Phase 8 - Repo-QA | Graph slices, symbol summaries, file/symbol lookup, provenance/confidence |
| Phase 9 - Fault localisation | File/symbol/import/test graph, blame chain, build/test evidence, stale index visibility |
| Phase 10 - Evaluation harness | Indexing fixture repos, run records, graph freshness metrics |
| Phase 11 - Patch review | Changed-symbol lookup, graph context around changed symbols, test evidence |
| Phase 12 - SAST repair | Graph nodes around alert locations, provenance-rich file/span evidence |
| Phase 13 - Bug-resolve | Investigate context: graph slices, blame, build/test evidence, summaries |
| Phase 14 - Implementation-check | Document/code graph links later, contract target symbols, snapshot-aware clause grounding |
| Phase 15 - Blast radius | Ego graph traversal around changed files/symbols |
| Phase 16 - Dynamic traces | Runtime trace node attachment points and observed-in edge targets |
| Phase 17 - Memory | Stable graph IDs and trajectory context references |
| Phase 18 - Release gates | Index completeness, stale/dirty snapshot rates, graph fixture metrics |
| Phase 19 - Distribution | File watcher/git hook integration, cache invalidation hardening, large graph chunking |

---

## 29. Exit Criteria Mapping

Source Phase 3 exit criterion:

- `graph_build(repo_path)` indexes a small Python repo.

Concrete acceptance:

- `python_basic` fixture produces repo, directory, file, module, class/function/method/test/build nodes and `contains`/`imports`/selected `tests` edges.
- Build creates a snapshot, graph facts, graph manifest, diagnostics, and run record.

Source Phase 3 exit criterion:

- `graph_update(repo_path)` updates changed files without rebuilding everything.

Concrete acceptance:

- Update detects changed files.
- Only affected file/symbol facts are superseded or rewritten.
- Unaffected file facts remain queryable.
- Summary and blame caches are invalidated only for affected files.

Source Phase 3 exit criterion:

- Graph slices include files, symbols, imports, tests, and provenance.

Concrete acceptance:

- File and symbol slice tests verify required node and edge classes.
- Slice payload includes snapshot IDs, confidence, derivation, and diagnostics.

Source Phase 3 exit criterion:

- Symbol summaries and blame chains can be cached, invalidated, and retrieved with snapshot provenance.

Concrete acceptance:

- Summary cache keys include snapshot identity.
- Blame records include repo, snapshot, file, artefact hash, and provenance.
- File changes invalidate relevant records.

Source Phase 3 exit criterion:

- Stale index state is visible.

Concrete acceptance:

- Repo status changes to stale when current worktree differs from latest indexed snapshot.
- Dirty snapshots produce warnings.
- Mixed graph slices report mixed status.

Source Phase 3 exit criterion:

- Graph build/update runs produce operational events and can be reviewed when an index is incomplete or stale.

Concrete acceptance:

- Build/update create run records and append events for scanner, snapshot, backends, diagnostics, skipped files, stale/dirty warnings, manifest generation, and final status.

---

## 30. Definition Of Done

Phase 3 is done when:

- `graph_build(repo_path)` works on a small Python repository fixture.
- `graph_update(repo_path)` updates changed files without rebuilding unaffected files.
- The file scanner emits file, directory, package/module nodes and containment edges.
- Git metadata and dirty worktree snapshots are captured.
- Git blame chains are collected or diagnostic failures are stored.
- Python AST backend emits module, symbol, import, test, and conservative call facts.
- Ctags and tree-sitter adapters are implemented as optional enrichers or cleanly reported unavailable.
- Build/test evidence detector finds pytest, package metadata, test directories, and CI files.
- Graph facts validate against Phase 1 schemas before storage.
- Graph facts are written through Phase 2 graph store.
- Graph manifests and chunk artefacts are generated.
- Graph slices include files, symbols, imports, tests, provenance, snapshot consistency, and truncation metadata.
- Symbol-summary cache records are keyed by snapshot and invalidated on file/symbol changes.
- Stale, dirty, partial, and mixed states are visible.
- Indexing runs produce operational events.
- Fixture tests cover full build, incremental update, stale state, partial backend failure, graph slices, summaries, blame, and manifests.

---

## 31. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Indexer tries to build a perfect call graph too early | Phase stalls and APIs churn | Keep Python MVP conservative; mark unresolved facts as diagnostics or low-confidence candidates |
| Backend availability differs across machines | Tests become flaky | Make ctags/tree-sitter optional enrichers; use fixture output where needed |
| Dirty worktree facts overwrite clean facts | Downstream workflows trust wrong snapshot | Store dirty snapshot IDs separately and include snapshot consistency in queries |
| Incremental update leaves stale edges | Fault localisation and patch review use old evidence | Supersede changed-file facts transactionally and mark uncertain dependencies stale |
| Summary text becomes treated as hard evidence | LLM-generated context bypasses graph evidence | Store summaries as low-confidence hybrid evidence and never as parser facts |
| Large graph dumps overload clients | MCP resources become unusable | Generate graph manifests and chunks; use slices for bounded contexts |
| Blame failures block indexing | Untracked/dirty files become impossible to index | Treat blame as optional evidence with diagnostics |
| Generated/vendor files pollute graph | Results become noisy and patch workflows may edit generated files | Mark generated/vendor files and skip or lower priority by policy |
| Operational events are incomplete | Index failures cannot be reviewed | Emit run events for scanner, snapshot, backends, diagnostics, skipped files, and final status |

---

## 32. Phase 3 Completion Report Template

When Phase 3 implementation is complete, report:

```text
Phase 3 completion report

Implemented:
- Indexing service:
- File scanner:
- Git metadata and snapshots:
- Blame-chain collector:
- Python AST backend:
- Ctags adapter:
- Tree-sitter adapter:
- Build/test evidence detector:
- Summary cache:
- Graph merge/write:
- Graph manifests:
- Graph slices:
- Operational events:
- CLI/internal commands:

Verification:
- Scanner tests:
- Git/snapshot tests:
- Python backend tests:
- Build/test evidence tests:
- Blame tests:
- Summary cache tests:
- Graph build integration:
- Graph update integration:
- Graph slice tests:
- Manifest tests:
- Operational event tests:
- Local verify command:

Exit criteria:
- graph_build indexes small Python repo:
- graph_update updates changed files incrementally:
- graph slices include files/symbols/imports/tests/provenance:
- summaries and blame cache with snapshot provenance:
- stale index state visible:
- build/update runs produce operational events:

Known limitations:
-

Follow-up for Phase 4:
-
```

---

## 33. Minimal First Slice Within Phase 3

If Phase 3 needs to be split further, implement this first:

1. `IndexingConfig`, `IndexingContext`, and `IndexingResult`.
2. File scanner and ignore policy.
3. Git metadata and clean/dirty snapshot capture.
4. Python AST backend for modules, functions, classes, and imports.
5. Build/test evidence detector for pytest and test directories.
6. Graph write path through Phase 2 store.
7. `graph_build(repo_path)` for `python_basic`.
8. Graph slice by file.
9. Basic graph manifest.
10. Indexing run record and events.

This minimal slice unblocks Phase 4 MCP resources for repos, graph manifests, graph slices, build evidence, and indexing status.
