# LLM-SCA Tooling Phase 9 Implementation Plan: Fault Localisation

> Date: 2026-05-09  
> Repository name: `evidence-sca`  
> Source plan: `llm-sca-tooling-implementation-plan.md`  
> Source architecture: `llm-sca-tooling-architecture.md`  
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 9 - Fault Localisation  
> Primary objective: rank likely root-cause locations and produce a bounded context set by implementing an issue text normalizer, a multi-signal candidate retrieval pipeline (keyword, semantic embeddings, SARIF proximity, blame/history prior), a graph-neighbour expansion stage, an optional SBFL/Ochiai prior, a bounded context assembler targeting the 6–10 file sweet spot, per-candidate reasoning chains (RGFL pattern), a ranking policy, an uncertainty model, and the `get_relevant_files` MCP tool — then lay the private `investigate` skill template foundation consumed by Phase 13 bug-resolve.

---

## 1. Phase Summary

Phases 3–8 built the evidence graph, the SARIF layer, cross-language plugins, and repo-QA. Phase 9 answers the first question in every repair workflow: *which files and symbols are most likely to contain the bug?* The quality of fault localisation dominates repair quality — `fl-context-2026` shows a 15–17× repair improvement from file-level localisation alone. Getting this right before Phase 13 introduces repair automation is essential.

The central rule for this phase is:

```text
Localisation quality is measured by evidence agreement, not model confidence.
High confidence requires convergence between semantic retrieval, graph/static evidence,
and at least one independent signal (SARIF proximity, blame prior, or memory hint).
Low agreement between retrieval and graph evidence must produce an uncertain localisation.
The default context budget is 6-10 files. Exceeding it requires an explicit uncertainty note.
```

Phase 9 should implement:

- Issue text normalizer: symptoms, expected behaviour, observed behaviour, mentioned APIs/files, error strings, and stack trace frames.
- Keyword retrieval against the graph index (file names, symbol names, docstrings, identifiers).
- Semantic embedding interface with per-symbol vector cache invalidated by `git_sha` / worktree-snapshot changes.
- SARIF proximity prior using Phase 6 alert store.
- Blame and history prior using Phase 8 blame chain records.
- Graph-neighbour expansion: callers, callees, imports, tests, documents, data-flow, and interface edges.
- Optional SBFL/Ochiai suspiciousness feature when coverage and failing tests are available.
- Bounded context assembler: graph slices, cached symbol summaries, SARIF/build/test evidence, and exact source spans only when required.
- Per-candidate reasoning chain scaffold (RGFL pattern) for LLM-driven ranking.
- Ranking policy combining all signals into a ranked candidate list.
- Uncertainty model: low signal agreement, stale index, budget exceeded.
- `get_relevant_files` MCP tool.
- Private `investigate` skill template foundation.
- Memory hint integration interface (stub; populated by Phase 17).

### Architecture Coverage

Phase 9 covers:

- F2 fault localisation and relevant-context discovery.
- `get_relevant_files` MCP tool.
- Private `investigate` skill template foundation.
- Embedding vector cache backing the `[ML-MODEL]` retrieval path.

### Inherited Paper Anchors

Use these anchors in Phase 9 issues, ADRs, retrieval design notes, and FL benchmark reports:

- `fl-context-2026`
- `rgfl`
- `arise`
- `locagent`
- `cosil`
- `hafixagent`
- `repo-aware-kg`
- `autocoderover`
- `agentless`

Adjacent anchors useful for specific component notes:

- `repograph`
- `codexgraph`
- `rig`
- `logiclens`
- `swe-qa-pro`

## Technology Stack

This is the first phase where the embeddings layer is activated. `fastembed` and `sqlite-vec` are **uncommented in `pyproject.toml` in this phase**; they must not appear as active imports in any earlier phase.

| Library / Tool | PyPI package | Version | Purpose in this phase |
|---|---|---|---|
| Python | — | >=3.12 | Language baseline; all async I/O via `asyncio.create_subprocess_exec` |
| uv | — | latest | Environment and dependency management |
| Pydantic v2 | `pydantic` | >=2.0 | `IssueText`, `CandidateFile`, `CandidateSymbol`, `LocalisationResult`, `ContextBundle`, `InvestigateInput/Output`, and all FL models; `extra="forbid"`, schemas via `model_json_schema()` |
| orjson | `orjson` | >=3.10 | Primary JSON I/O for serialising `EmbeddingVector` cache entries, `ContextBundle` payloads, and `LocalisationResult` artefacts |
| SQLModel + Alembic | `sqlmodel`, `alembic` | >=0.0.21, >=1.13 | `embedding_vectors` table (Section 8.3 DDL) and schema migration; async sessions via `aiosqlite` |
| aiosqlite | `aiosqlite` | >=0.20 | Async SQLite driver for vector cache and workspace store reads |
| asyncpg | `asyncpg` | >=0.29 | Async PostgreSQL driver; used when storage backend is Postgres (same interface, swap via config) |
| NetworkX | `networkx` | >=3.3 | In-memory graph traversal for graph-neighbour expansion (Section 11); ego-graph queries and hop-decay traversal |
| fastembed | `fastembed` | >=0.3 | **ACTIVATED in this phase** (uncomment in `pyproject.toml`); local embeddings with no external API key; default model `BAAI/bge-small-en-v1.5`; used in `local_adapter.py`; `NullAdapter` used in CI and tests |
| sqlite-vec | `sqlite-vec` | >=0.1 | **ACTIVATED in this phase** (uncomment in `pyproject.toml`); SQLite vector search extension; cosine similarity ANN search over the `embedding_vectors` table |
| pgvector | `pgvector` | — | PostgreSQL production alternative to `sqlite-vec`; same interface via storage abstraction; activated by config when Postgres backend is selected |
| FastMCP | `fastmcp` | >=2.0 | MCP server framework for the `get_relevant_files` tool handler |
| FastAPI | `fastapi` | >=0.115 | HTTP layer for the MCP server |
| pytest | `pytest` | >=8.0 | Test runner for all Phase 9 unit and integration tests |
| pytest-asyncio | `pytest-asyncio` | >=0.23 | Async test support; `asyncio_mode="auto"` in `pyproject.toml` |
| pytest-cov | `pytest-cov` | >=5.0 | Coverage measurement; core `fl/` modules target >95% |
| pytest-xdist | `pytest-xdist` | >=3.5 | Parallel test execution (`-n auto`) for the integration test suite |
| tox | `tox` | >=4.0 | Multi-version matrix for reproducibility across Python versions |
| import-linter | `import-linter` | >=2.1 | Architectural layering enforcement; `fl/` must not import from `mcp_server/` directly |

**Activation notes:**

- `fastembed` and `sqlite-vec` are listed but commented out in `pyproject.toml` through Phase 8. Phase 9 removes those comments. Any `import fastembed` or `import sqlite_vec` before Phase 9 is a layering error.
- The vector cache key is `(repo_id, symbol_path, git_sha)` — invalidate when the file changes (Section 8.2).
- `pgvector` is the production swap for `sqlite-vec`; the storage abstraction layer selects the backend via config, so application code does not branch on backend type.
- All async database I/O uses `asyncio.create_subprocess_exec` for subprocess calls and the SQLModel async session for store queries. No synchronous blocking I/O in the FL hot path.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 9 depends on:

- Phase 1 schemas:
  - Graph node types: `file`, `module`, `class`, `function`, `method`, `variable`, `test`, `document`, `design_clause`, `sast_rule`, `sarif_alert`, `http_route`, `websocket_event`, `idl_interface`.
  - Graph edge types: `contains`, `imports`, `calls`, `dataflow`, `tests`, `documents`, `warned_by`, `exposes`, `consumes`, `ffi`.
  - Provenance, confidence, and derivation enums.
  - Evidence-strength ordering.
- Phase 2 stores:
  - Graph store with fetch-by-type, fetch-by-file/span, neighbour queries, and ego-graph queries.
  - Artefact registry.
  - Snapshot ledger.
  - Workspace metadata store.
- Phase 3/5 indexing:
  - File and symbol nodes with spans.
  - Call, import, and dataflow edges.
  - Symbol summary cache (lazy, keyed by repo+symbol+snapshot).
  - Build and test evidence nodes.
- Phase 6 SARIF:
  - `get_alerts_for_file` and `get_alerts_for_symbol` query interfaces.
  - Normalized severity and rule family.
  - `warned_by` edges for graph-linked suspects.
- Phase 7 plugins:
  - `trace_cross_language` traversal engine.
  - `exposes`, `consumes`, `implements`, `ffi` edges.
- Phase 8 repo-QA:
  - `git_blame_chain` tool and blame-chain records.
  - Deterministic file and symbol lookup.
  - `BehaviourTraceModule` (reusable for cross-language expansion).

### Phase Outputs

Phase 9 should produce:

- Issue text normalizer and `IssueText` model.
- `CandidateFile` and `CandidateSignal` models.
- `CandidateSymbol` model with reasoning chain field.
- `LocalisationResult` and `ContextBundle` models.
- Keyword retrieval module.
- Embedding interface (abstract + null adapter for testing).
- Vector cache with `git_sha`-based invalidation.
- SARIF proximity prior module.
- Blame and history prior module.
- Graph-neighbour expansion module.
- SBFL/Ochiai feature module (gated by availability).
- Bounded context assembler with 6–10 file budget.
- RGFL reasoning chain scaffold.
- Ranking policy with signal weighting.
- Uncertainty model.
- `get_relevant_files` MCP tool.
- Private `investigate` skill template foundation (data flow + prompt template stub).
- Memory hint integration interface stub.

### Non-Goals

Do not implement these in Phase 9:

- Full repair workflow. That is Phase 13.
- Trajectory memory retrieval. That is Phase 17.
- Dynamic trace capture. That is Phase 16.
- Evaluation harness benchmark runner. That is Phase 10.
- Patch review. That is Phase 11.
- SAST repair. That is Phase 12.
- Fine-tuning the embedding model. That is Phase 18.
- Production embedding model hosting; Phase 9 only requires an abstract embedding interface and a null adapter.

Phase 9 delivers the FL infrastructure that Phase 13 and Phase 10 consume. It does not complete the end-to-end repair loop.

---

## 3. Recommended File Layout

```text
src/evidence_sca/
  fl/
    __init__.py
    issue.py
    keyword_retrieval.py
    embedding_interface.py
    vector_cache.py
    sarif_prior.py
    blame_prior.py
    graph_expansion.py
    sbfl.py
    context_assembler.py
    reasoning.py
    ranking.py
    uncertainty.py
    localisation.py
    investigate.py
    memory_stub.py

  fl/embedding_adapters/
    __init__.py
    null_adapter.py
    openai_adapter.py
    local_adapter.py

  mcp_server/tools/
    fl.py

tests/
  fl/
    fixtures/
      issues/
        python_null_deref.jsonl
        ts_api_mismatch.jsonl
        cpp_memory_leak.jsonl
        cross_language_regression.jsonl
        no_stack_trace.jsonl
        stack_trace_only.jsonl
      repos/
        fl_python_repo/
          src/
          tests/
          pyproject.toml
    test_issue.py
    test_keyword_retrieval.py
    test_embedding_interface.py
    test_vector_cache.py
    test_sarif_prior.py
    test_blame_prior.py
    test_graph_expansion.py
    test_sbfl.py
    test_context_assembler.py
    test_reasoning.py
    test_ranking.py
    test_uncertainty.py
    test_localisation.py
    test_investigate.py
    test_memory_stub.py
    test_get_relevant_files.py
    test_integration.py
```

---

## 4. Issue Text Normalizer

### 4.1 Purpose

`issue.py` converts a raw issue report into a structured `IssueText` that downstream retrieval and ranking components can query without re-parsing the raw text.

### 4.2 `IssueText` Model

```text
IssueText
  issue_id : str
  raw_text : str
  normalized_text : str
  symptoms : list[str]
  expected_behaviour : str | None
  observed_behaviour : str | None
  mentioned_apis : list[str]
  mentioned_files : list[str]
  mentioned_symbols : list[str]
  error_strings : list[str]
  stack_trace_frames : list[StackFrame]
  repos : list[str] | None
  severity_hint : str | None
  language_hints : list[str]
  submitted_ts : str

StackFrame
  file_path : str | None
  line : int | None
  function_name : str | None
  module_name : str | None
  raw_text : str
```

### 4.3 Normalizer Stages

**Stage 1 — Structure detection:**
- Detect GitHub-style issue templates: `## Steps to reproduce`, `## Expected`, `## Actual`.
- Detect Jira-style: `h2. Description`, `h2. Steps`.
- Detect plain-text issues: best-effort section extraction.

**Stage 2 — Stack trace extraction:**
- Python: `Traceback (most recent call last):` followed by `File "...", line N, in function`.
- TypeScript/JavaScript: `at <function> (<file>:<line>:<col>)`.
- C/C++: `#N 0x... in <function> (<file>:<line>)`.
- Each frame maps to a `StackFrame` record.

**Stage 3 — Entity extraction:**
- Code tokens: camelCase, snake_case, PascalCase strings extracted as `mentioned_symbols`.
- Path-like tokens: strings containing `/` or `.py`, `.ts`, `.cpp` suffixes → `mentioned_files`.
- Error strings: lines matching `Error:`, `Exception:`, `panic:`, `SIGSEGV`, `undefined`, `null` → `error_strings`.
- API names: tokens matching registered symbol names or interface names → `mentioned_apis`.

**Stage 4 — Language hint detection:**
- Stack trace file extensions.
- Error message patterns: `NullPointerException` → Java, `AttributeError` → Python, `TypeError: cannot read` → JavaScript/TypeScript.

**Stage 5 — Normalization:**
- Remove Markdown formatting.
- Remove URLs (preserve domain as a hint).
- Collapse whitespace.
- Preserve code blocks verbatim.

### 4.4 Issue Text Rules

- Raw text is always preserved.
- Normalization is deterministic.
- Stack frames are extracted as `StackFrame` objects, not strings.
- `mentioned_files` are repo-relative paths where possible; otherwise raw.
- `mentioned_symbols` are code token strings, not resolved node IDs.

### 4.5 Issue Normalizer Tests

Required tests:

- GitHub-style template: sections extracted correctly.
- Python stack trace: all frames parsed.
- JS/TS stack trace: frames with file and line.
- C++ gdb stack trace: frames parsed.
- Error string extraction.
- Mentioned file paths extracted.
- Mentioned symbol tokens extracted.
- Language hint from stack trace extension.
- Missing sections return `None`, not empty string.

---

## 5. Candidate Retrieval Architecture

### 5.1 Multi-Signal Design

Phase 9 uses a multi-signal retrieval architecture. Each signal independently produces a ranked candidate list. Signals are then merged and weighted by the ranking policy.

Signals:

| Signal | Mode | Source | Confidence cap |
|---|---|---|---|
| Keyword retrieval | `[PY-CODE]` | Graph index (file/symbol names, identifiers) | `analyser` |
| Semantic embedding | `[ML-MODEL]` | Embedding vector cache | `analyser` |
| SARIF proximity | `[PY-CODE]` | Phase 6 SARIF store | `analyser` |
| Blame/history prior | `[PY-CODE]` | Phase 8 blame records | `heuristic` |
| Graph-neighbour expansion | `[PY-CODE]` | Phase 2/3/5/7 graph store | `parser` (for direct `warned_by` edges) |
| SBFL/Ochiai | `[PY-CODE]` (optional) | Test coverage data | `analyser` (when coverage available) |
| Memory hints | `[HYBRID]` stub | Phase 17 (stub in Phase 9) | `heuristic` |

### 5.2 Signal Independence

Each signal runs independently before merging. No signal blocks another. If a signal is unavailable (e.g., embedding model not configured), it contributes zero weight to the final ranking rather than crashing.

### 5.3 `CandidateFile` Model

```text
CandidateFile
  candidate_id : str
  file_path : str
  repo_id : str
  node_id : str
  signals : list[CandidateSignal]
  combined_score : float     # Weighted sum of signal scores
  confidence : ConfidenceLevel
  evidence_summary : str | None
  snapshot_id : str
  is_generated : bool         # True if Phase 7 marks file as generated

CandidateSignal
  signal_type : SignalType    # keyword, embedding, sarif, blame, graph, sbfl, memory
  raw_score : float           # Signal-specific raw score (0.0–1.0)
  weight : float              # Applied weight from ranking policy
  weighted_score : float
  evidence : str              # Short explanation of why this signal fires
  source_refs : list[str]     # Graph node IDs, alert IDs, commit SHAs
  confidence : ConfidenceLevel

SignalType enum
  KEYWORD
  EMBEDDING
  SARIF_PROXIMITY
  BLAME_HISTORY
  GRAPH_NEIGHBOUR
  SBFL
  MEMORY_HINT
```

### 5.4 `CandidateSymbol` Model

Symbol-level candidates are produced after file-level ranking by narrowing the top-N files.

```text
CandidateSymbol
  candidate_id : str
  symbol_node_id : str
  symbol_path : str
  symbol_type : str       # function, method, class, variable
  file_path : str
  repo_id : str
  span : Span
  signals : list[CandidateSignal]
  combined_score : float
  confidence : ConfidenceLevel
  reasoning_chain : str | None    # RGFL per-candidate explanation (LLM-generated)
  uncertainty : str | None
```

### 5.5 Pipeline Overview

```text
IssueText
  -> keyword_retrieval   -> CandidateFile list (keyword)
  -> embedding_retrieval -> CandidateFile list (embedding)
  -> sarif_prior         -> CandidateFile list (sarif)
  -> blame_prior         -> CandidateFile list (blame)
  -> graph_expansion     -> CandidateFile list (graph neighbours)
  -> sbfl_prior          -> CandidateFile list (sbfl, optional)
  -> memory_stub         -> CandidateFile list (memory, stub)
  -> RankingPolicy.merge -> CandidateFile list (combined, sorted)
  -> BoundedContextAssembler (top-N files)
  -> ReasoningChainScaffold (per-candidate LLM reasoning)
  -> UncertaintyModel
  -> LocalisationResult
```

---

## 6. Keyword Retrieval

### 6.1 Purpose

`keyword_retrieval.py` provides a fast, deterministic, zero-dependency candidate retrieval path that works even when no embedding model is available.

### 6.2 Keyword Extraction From `IssueText`

Sources for query terms:

- `error_strings`: high-weight exact match against file/symbol names.
- `mentioned_symbols`: exact and fuzzy match against graph symbol names.
- `mentioned_files`: path-suffix match against graph file nodes.
- Stack trace `function_name` and `file_path` fields.
- `mentioned_apis`: match against interface operation names (Phase 7).
- Normalized issue text tokens: tokenize by word boundary, filter stop words, apply stemming.

### 6.3 Search Targets

Keyword search runs against:

1. **File node names**: base name of `file` nodes (e.g., `auth.py`, `UserService.ts`).
2. **Symbol names**: all `function`, `method`, `class`, `variable` node names.
3. **Module names**: `module` node names.
4. **Symbol summaries**: summary text from Phase 3 summary cache, when available.
5. **Document node titles**: `document` and `design_clause` node titles where indexed.

### 6.4 Scoring

BM25-style term frequency/inverse document frequency scoring:

- TF: term frequency within the searchable text for a node.
- IDF: inverse frequency across all nodes in all registered repos.
- Score normalized to 0.0–1.0.
- File-level score: max over all symbol scores within the file.

### 6.5 Stack Trace Bonus

When `mentioned_files` or `mentioned_symbols` exactly match graph nodes:

- Exact file path match: bonus of +0.5 (capped at 1.0 total).
- Exact symbol name match: bonus of +0.4.
- Module-qualified symbol match: bonus of +0.3.

Stack trace matches are given higher weight than keyword matches because they are direct program evidence.

### 6.6 Keyword Retrieval Tests

Required tests:

- Error string `"NullPointerException in UserService.validate"` → `UserService` file ranked first.
- Exact file path in issue text → 100% recall for that file.
- Stack trace function name match → bonus applied.
- No matches: empty result, not crash.
- Stemming: "validating" matches "validate" symbol.
- Multi-repo keyword search returns results from all repos.

---

## 7. Semantic Embedding Interface

### 7.1 Purpose

`embedding_interface.py` defines the abstract boundary for embedding-based retrieval. Phase 9 requires this interface but does not mandate a specific embedding model. A null adapter enables full pipeline testing without a model endpoint.

### 7.2 `EmbeddingInterface`

```text
EmbeddingInterface (abstract)
  model_id : str
  dimensions : int

  is_available() -> bool
    # Fast check; no network call.

  embed_text(text: str, context_hint: str | None) -> EmbeddingVector
    # May call model API. Raises EmbeddingUnavailable if not available.

  embed_batch(texts: list[str]) -> list[EmbeddingVector]
    # Batch embed; more efficient than repeated embed_text calls.

  similarity(a: EmbeddingVector, b: EmbeddingVector) -> float
    # Cosine similarity. Range: -1.0 to 1.0.

  top_k_similar(
    query: EmbeddingVector,
    corpus: list[EmbeddingVector],
    k: int,
  ) -> list[tuple[int, float]]
    # Return (index, similarity) sorted descending.
```

### 7.3 `EmbeddingVector`

```text
EmbeddingVector
  vector : list[float]
  model_id : str
  dimensions : int
  text_hash : str     # SHA-256 of the input text; for cache key
  produced_ts : str
```

### 7.4 Null Adapter

`null_adapter.py` implements `EmbeddingInterface` for tests and configurations without a model.

Behavior:

- `is_available()` returns `False`.
- `embed_text` raises `EmbeddingUnavailable`.
- When a null adapter is registered, the embedding signal contributes zero weight.
- The pipeline continues without embedding retrieval.

### 7.5 Retrieval Path

When embedding retrieval is available:

1. Embed the `IssueText.normalized_text` (and error strings) as a query vector.
2. Retrieve top-K symbol vectors from the vector cache.
3. Map to file-level candidates by grouping symbol results by file.
4. Score: max symbol similarity within the file.

### 7.6 Configuration

```text
EmbeddingConfig
  model_id : str
  adapter : str               # null, openai, local, custom
  dimensions : int
  batch_size : int
  timeout_seconds : float
  max_symbols_to_embed : int  # Limit for large repos
  similarity_threshold : float  # Minimum similarity to include
```

### 7.7 Embedding Interface Tests

Required tests:

- Null adapter: `is_available()` returns False.
- Null adapter: embedding signal contributes zero weight.
- `EmbeddingVector` round-trips through serialization.
- `top_k_similar` returns correct ordering.
- `embed_batch` produces same results as repeated `embed_text`.

---

## 8. Embedding Vector Cache

### 8.1 Purpose

`vector_cache.py` persists per-symbol embedding vectors, keyed by `(node_id, git_sha)`. When the graph advances to a new commit, old vectors are invalid and must be re-embedded.

### 8.2 Cache Key And Invalidation

Cache key: `(node_id, model_id, git_sha)`.

Invalidation rules:

- When `graph_update` runs for a file, invalidate all vector cache entries for nodes in that file.
- When the repo's `git_sha` advances, all vectors for that repo are stale.
- Worktree snapshot vectors are keyed by `worktree_snapshot_id` and expire after the snapshot is resolved.
- Stale vectors must not be used; the caller must re-embed or skip the embedding signal.

### 8.3 Cache Storage

Recommended storage table (Phase 2 workspace store):

```sql
CREATE TABLE embedding_vectors (
  cache_key TEXT PRIMARY KEY,
  node_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  git_sha TEXT NOT NULL,
  worktree_snapshot_id TEXT,
  vector_blob BLOB NOT NULL,
  dimensions INTEGER NOT NULL,
  text_hash TEXT NOT NULL,
  produced_ts TEXT NOT NULL,
  expires_ts TEXT
);

CREATE INDEX idx_embedding_node ON embedding_vectors(node_id, model_id);
CREATE INDEX idx_embedding_git_sha ON embedding_vectors(git_sha);
```

### 8.4 Cache Interface

```text
VectorCache
  store(node_id: str, model_id: str, git_sha: str, vector: EmbeddingVector) -> None
  get(node_id: str, model_id: str, git_sha: str) -> EmbeddingVector | None
  invalidate_file(file_path: str, repo_id: str, new_git_sha: str) -> int
  invalidate_repo(repo_id: str, new_git_sha: str) -> int
  purge_expired() -> int
  stats() -> VectorCacheStats

VectorCacheStats
  total_entries : int
  valid_entries : int
  stale_entries : int
  hit_rate : float
  last_purge_ts : str | None
```

### 8.5 Cache Integration With Graph Update

`graph_update` (Phase 3/4) must call `VectorCache.invalidate_file(...)` for each file that is re-indexed. Phase 9 hooks into the existing graph-update event stream.

### 8.6 Vector Cache Tests

Required tests:

- Store and retrieve a vector.
- `get` with wrong `git_sha` returns None.
- `invalidate_file` removes all entries for that file path and repo.
- `invalidate_repo` removes all entries for that repo.
- Stats reflect cache entries correctly.
- `purge_expired` removes expired entries.

---

## 9. SARIF Proximity Prior

### 9.1 Purpose

`sarif_prior.py` uses Phase 6 SARIF alert data as a suspicion prior. Files with alerts matching the issue's error strings, rule families, or CWE patterns are ranked higher.

### 9.2 Proximity Matching

Match between `IssueText` and SARIF alerts:

1. **Error string match**: if `issue.error_strings` contains text matching an alert message → high weight.
2. **CWE family match**: if `issue.raw_text` mentions `CWE-NNN` or a vulnerability class that maps to a SARIF rule family → medium weight.
3. **Symbol name match**: if `issue.mentioned_symbols` matches a symbol bound by a `warned_by` edge from a SARIF alert → high weight.
4. **Rule family heuristic**: if `issue.raw_text` contains security keywords and the file has active `high` or `critical` severity alerts → low weight.

### 9.3 SARIF Prior Score

Per-file SARIF prior score:

```text
sarif_score(file) =
  sum over matching_alerts of:
    alert.normalized_severity_weight * match_type_weight
  normalized to [0, 1]

severity_weights:
  critical = 1.0
  high     = 0.8
  medium   = 0.5
  low      = 0.2
  info     = 0.1

match_type_weights:
  error_string_match  = 1.0
  symbol_match        = 0.9
  cwe_match           = 0.7
  rule_family_hint    = 0.3
```

### 9.4 Alert Currency Check

Rules:

- Only active alerts (not superseded, not from a stale SARIF run) contribute to the prior.
- If the most recent SARIF run predates the current graph snapshot, emit a `SARIF_STALE` diagnostic.
- Suppressed alerts contribute zero weight.

### 9.5 SARIF Prior Tests

Required tests:

- Error string match → correct file scored high.
- Symbol name match → file with `warned_by` edge scored high.
- CWE family match → medium weight.
- Suppressed alert → zero weight.
- Stale SARIF run → diagnostic emitted.
- No matching alerts → empty result, no crash.

---

## 10. Blame And History Prior

### 10.1 Purpose

`blame_prior.py` uses git blame records and commit history to surface files recently changed in a way likely related to the reported issue.

### 10.2 HAFixAgent Pattern

`hafixagent` motivates blame as a cheap, near-free FL signal. Key insight: regressions often appear in files recently modified by the same author or in the same commit batch that introduced the breaking change. Issue text often references "after the last release" or "since the update to X".

### 10.3 History Signals

**Recent-change proximity:**

1. Identify commits that mention `issue.mentioned_symbols`, `issue.error_strings`, or `issue.mentioned_apis` in their commit message.
2. Score files touched by those commits by recency and message relevance.

**Author co-change:**

1. If the issue mentions specific behaviour that correlates with a commit author, weight files changed by that author in the recent window.
2. Implementation-level: use blame author field and window the last N commits.

**Churn proximity:**

1. Files with high recent churn (many edits in the last `K` commits) are more likely to be the source of a regression.
2. Churn score: number of commits touching the file in the last 30 days / average file churn.

### 10.4 Blame Prior Score

```text
blame_score(file) =
  w_recency * recency_decay(last_commit_ts)
  + w_message_match * message_keyword_match(commit_messages)
  + w_churn * churn_ratio(file, window)
normalized to [0, 1]

Default weights:
  w_recency       = 0.4
  w_message_match = 0.4
  w_churn         = 0.2

recency_decay(ts) = exp(-hours_since_commit / 168)  # 1-week half-life
```

### 10.5 Blame Data Source

Blame prior reads from Phase 8 `BlameEntry` and `CommitRecord` records, not from live `git blame` execution. If blame records are stale, emit a diagnostic and apply zero weight for the affected files.

### 10.6 Blame Prior Tests

Required tests:

- Commit mentioning issue keyword → file from that commit scored higher.
- High-churn file → churn score applied.
- Stale blame records → diagnostic, zero weight.
- No recent commits mentioning keywords → empty result.
- Recency decay applied correctly.

---

## 11. Graph-Neighbour Expansion

### 11.1 Purpose

`graph_expansion.py` expands an initial candidate set through the graph. If file A is a candidate, then its callers, callees, test modules, document links, and interface peers become secondary candidates.

### 11.2 Expansion Steps

Given an initial `CandidateFile` list from retrieval signals:

1. Fetch symbol nodes for each candidate file.
2. For each symbol node, expand via:
   - `calls` edges: direct callers and callees (up to depth 2).
   - `imports` edges: modules imported by and importing the symbol's file.
   - `tests` edges: test files that exercise symbols in the candidate file.
   - `documents` edges: spec/doc nodes referencing the candidate.
   - `dataflow` edges (where available from Phase 6 CodeQL/Semgrep taint): data-flow neighbours.
   - `warned_by` edges: SARIF-linked files adjacent to the candidate.
   - Interface edges (`exposes`, `consumes`, `ffi`): cross-language peers via Phase 7.
3. Aggregate expansion scores: each expanded file's expansion score is the source candidate score multiplied by a hop-decay factor.
4. Merge expanded candidates with original candidates; higher score wins per file.

### 11.3 Expansion Limits

Rules:

- Expand at most 2 hops from the initial candidates.
- Expansion adds at most `max_expansion_files` new candidates (default: 20).
- Cross-language expansion (via Phase 7 plugins) is enabled when plugins are registered.
- Generated files (Phase 7 generated artifact tracking) receive reduced expansion weight.

### 11.4 Hop Decay

```text
expansion_score(file, hop_n) = source_candidate_score * decay^hop_n

Default decay = 0.6
Hop 1: score * 0.6
Hop 2: score * 0.36
```

### 11.5 Cross-Language Expansion

When a top candidate symbol is near a cross-language boundary (Phase 7 `exposes`, `consumes`, or `ffi` edge):

- Call `CrossLanguageTraverser.traverse(symbol_node_id)` with `max_hops=2`.
- Add reached nodes' files as expansion candidates.
- Label these with `signal_type=GRAPH_NEIGHBOUR` and `evidence="cross_language_expansion"`.

### 11.6 Graph Expansion Tests

Required tests:

- Caller of a candidate file added as hop-1 expansion.
- Test file linked via `tests` edge added as expansion.
- Cross-language expansion adds TS client for Python handler candidate.
- Expansion beyond max_files is truncated.
- Generated files receive reduced weight.
- Hop-decay applied correctly.

---

## 12. SBFL/Ochiai Feature

### 12.1 Purpose

`sbfl.py` computes an Ochiai suspiciousness score when test coverage and failing tests are available. This is an optional, additive prior — not a replacement for other signals.

### 12.2 Availability Check

SBFL is available when:

- A failing test exists (passed to `get_relevant_files` as `failing_tests`).
- Coverage data in LCOV, Cobertura, or JSON format is present in the workspace.
- The coverage report covers the target repo.

If any of these are missing, SBFL contributes zero weight with a diagnostic.

### 12.3 Ochiai Formula

Per method/symbol in the candidate set:

```text
ef = number of failing tests that execute this code location
ep = number of passing tests that execute this code location
nf = number of failing tests that do NOT execute this code location
np = number of passing tests that do NOT execute this code location

ochiai(ef, ep, nf, np) = ef / sqrt((ef + nf) * (ef + ep))

Edge cases:
  (ef + nf) == 0  → 0.0 (location never executed by failing tests)
  (ef + ep) == 0  → 0.0 (location never executed at all)
```

### 12.4 Coverage Source Integration

Supported coverage formats:

- **LCOV**: parse `*.lcov` or `lcov.info` files.
- **Cobertura XML**: parse `coverage.xml`.
- **JSON coverage** (coverage.py): parse `.coverage.json`.
- **Clang GCOV/LLVM LCOV**: parse from `llvm-cov export`.

Coverage parser produces:

```text
CoverageRecord
  file_path : str
  line_coverage : dict[int, int]   # line -> execution count
  branch_coverage : dict[tuple[int, int], bool] | None
  snapshot_id : str
```

### 12.5 SBFL Score Aggregation

File-level SBFL score: max Ochiai across all covered symbols in the file.

### 12.6 SBFL Tests

Required tests:

- Ochiai formula: ef=3, ep=1, nf=0, np=3 → correct score.
- LCOV file parsed correctly for fixture repo.
- Cobertura XML parsed.
- No coverage → SBFL contributes zero weight, diagnostic emitted.
- No failing tests → SBFL unavailable, diagnostic emitted.
- File-level score is max over symbols.

---

## 13. Bounded Context Assembler

### 13.1 Purpose

`context_assembler.py` takes the ranked candidate file list and assembles a bounded `ContextBundle` for consumption by the reasoning chain and by Phase 13 repair workflows.

### 13.2 Context Budget

The default context budget is **6 to 10 files**, derived from `fl-context-2026`. This is a configurable soft limit.

Budget rules:

- Default: `max_files = 8` (midpoint of the 6–10 range).
- Hard maximum: `max_files = 20` (requires explicit override).
- Exceeding the default produces an `uncertainty` note: "Context exceeds recommended 6-10 file budget. Localisation confidence reduced."
- Budget is tuned by: language target, repository size, RDS feature vector (from Phase 10), and measured FL accuracy.

### 13.3 Context Assembly Per File

For each top-N candidate file:

1. **Graph slice**: call `get_graph_slice(file_path, edge_types=["calls","imports","dataflow","tests","documents","warned_by"])`. Bounded to the graph slice size limit from Phase 4.
2. **Symbol summaries**: retrieve from Phase 3 summary cache for all symbols in the file. Low-confidence summaries are included but tagged as `heuristic`.
3. **SARIF alerts**: call Phase 6 `get_alerts_for_file` for active, non-suppressed alerts.
4. **Build/test evidence**: retrieve `build_target` and `test` nodes linked to the file.
5. **Blame entries**: retrieve the most recent N blame entries for the file (default N=3).
6. **Exact source spans**: retrieve only when a specific line is referenced by a stack trace frame or SARIF alert. Never retrieve the full file content.

### 13.4 `ContextBundle`

```text
ContextBundle
  files : list[ContextFileEntry]
  total_graph_nodes : int
  total_graph_edges : int
  total_symbol_summaries : int
  total_sarif_alerts : int
  budget_used : ContextBudget
  snapshot_ids : dict[str, str]
  is_over_budget : bool

ContextFileEntry
  candidate_file : CandidateFile
  graph_slice : GraphSlice
  symbol_summaries : list[SymbolSummary]
  sarif_alerts : list[NormalizedAlert]
  build_test_evidence : list[GraphNodeRef]
  blame_entries : list[BlameEntry]
  exact_spans : list[CodeSpan]

ContextBudget
  max_files : int
  actual_files : int
  max_graph_nodes : int
  actual_graph_nodes : int
  max_symbol_summaries : int
  actual_symbol_summaries : int
  token_estimate : int | None

CodeSpan
  file_path : str
  start_line : int
  end_line : int
  content : str           # Bounded; never the full file
  node_id : str | None
  confidence : ConfidenceLevel
  reason : str            # Why this span was included
```

### 13.5 Content Span Rules

Exact source span rules (inherited from Phase 8 evidence citation rules):

- Maximum 10 lines per span.
- Spans included only when: the span is referenced by a stack trace frame, a SARIF alert location, or a `warned_by` edge target.
- Full file content is never included in the context bundle.
- Span retrieval requires `confidence >= heuristic` for the referencing evidence.

### 13.6 Context Assembler Tests

Required tests:

- Top-8 candidates produce a context bundle with 8 `ContextFileEntry` items.
- Over-budget context (>10 files) includes uncertainty note.
- Graph slice retrieved for each file.
- Symbol summaries included.
- SARIF alerts included for files with active alerts.
- Exact span included for stack trace frame line.
- Full file content not included.
- Stale summary tagged as `heuristic`.

---

## 14. Candidate Explanation And RGFL Reasoning

### 14.1 Purpose

`reasoning.py` implements the RGFL (Reason-Generate-Fault-Localise) pattern: for each candidate, the reasoning chain articulates *why* the candidate is relevant before a ranking is produced. This prevents ranking from being based solely on similarity scores.

### 14.2 Reasoning Chain Scaffold

The reasoning chain scaffold prepares the evidence for per-candidate LLM explanation.

Per-candidate reasoning input:

```text
CandidateReasoningInput
  candidate_file : CandidateFile
  context_entry : ContextFileEntry
  issue_text : IssueText
  signals_summary : str        # Condensed signal evidence
  graph_path_to_issue : str | None  # If there is a graph path between issue symbols and candidate
```

LLM is given the `CandidateReasoningInput` for each candidate and asked to:

1. State the signal evidence linking the issue to this file.
2. State the graph/static evidence (calls, data-flow, SARIF alerts).
3. State any counter-evidence (why this candidate might be incorrect).
4. Produce a brief reasoning chain (2–3 sentences).

Rules:

- The reasoning chain is generated per-candidate before the final ranking is requested.
- LLM must cite evidence from the `signals_summary` and `context_entry`.
- LLM may not invent file paths or symbol names not present in the inputs.
- The reasoning chain is stored in `CandidateSymbol.reasoning_chain`.

### 14.3 Reasoning Without LLM

When LLM synthesis is disabled (budget mode, no model configured):

- `reasoning_chain` is assembled deterministically from signal evidence strings.
- Format: `"Keyword match: <keyword> found in symbol <name>. SARIF: <N> alerts. Blame: modified <N> days ago."`.
- `derivation = "deterministic"`.

### 14.4 Evidence Grounding Enforcement

Rules:

- LLM-generated reasoning chains are validated post-generation to ensure all cited file paths exist in the `context_entry`.
- Invalid citations (hallucinated paths) are stripped from the reasoning chain and flagged as a diagnostic.
- Reasoning chains without any valid evidence citation are marked as `ungrounded` and the candidate's confidence is downgraded to `heuristic`.

### 14.5 Reasoning Tests

Required tests:

- Deterministic reasoning chain assembled from signal evidence.
- LLM reasoning chain validated against context entry.
- Hallucinated file path stripped and flagged.
- Ungrounded reasoning chain: candidate confidence downgraded.

---

## 15. Ranking Policy

### 15.1 Purpose

`ranking.py` merges the multi-signal candidate lists into a single ranked list.

### 15.2 Ranking Algorithm

Linear combination of weighted signals:

```text
combined_score(file) =
  Σ (signal.raw_score * policy.weight[signal.signal_type])
  / Σ (policy.weight[signal.signal_type] * signal_available_flag)
```

Normalization: divide by the sum of weights for *available* signals only, so missing signals don't penalise candidates.

### 15.3 Default Signal Weights

```text
DEFAULT_SIGNAL_WEIGHTS = {
  KEYWORD:          0.25,
  EMBEDDING:        0.30,
  SARIF_PROXIMITY:  0.20,
  BLAME_HISTORY:    0.10,
  GRAPH_NEIGHBOUR:  0.10,
  SBFL:             0.05,
  MEMORY_HINT:      0.00,  # Zero until Phase 17 populates memory
}
```

Rules:

- Weights sum to 1.0 when all signals are available.
- Missing signals: their weight is redistributed proportionally to available signals.
- Weights are configurable per workspace.

### 15.4 Tie Breaking

Tie-breaking order:

1. Number of independent signals agreeing (more agreement = ranked higher).
2. Combined SARIF + graph signal (static evidence preferred over pure semantic).
3. File recency (more recently modified files ranked higher on ties).

### 15.5 Agreement Score

```text
agreement_score(file) =
  number of signal types with raw_score > 0.3
  / total number of available signal types

Range: 0.0–1.0
High agreement (>= 0.6): multiple independent signals converge → confidence `analyser`
Low agreement (< 0.3): single or no signals → confidence `heuristic`
```

### 15.6 Top-N Selection

After ranking:

- Select top-N files by combined score (N = `max_files` from context budget).
- Discard candidates with `combined_score < minimum_threshold` (default: 0.05).
- Generated files are retained but labeled with `is_generated=True` and ranked after non-generated files at the same score.

### 15.7 Ranking Tests

Required tests:

- Two signals agreeing → higher combined score than one signal alone.
- Missing signal redistributes weight.
- Generated file ranked after non-generated at same score.
- Minimum threshold filters low-score candidates.
- Agreement score > 0.6 → `analyser` confidence.
- Agreement score < 0.3 → `heuristic` confidence.

---

## 16. Uncertainty Model

### 16.1 Purpose

`uncertainty.py` computes and attaches uncertainty notes to the localisation result.

### 16.2 Uncertainty Conditions

Uncertainty note is attached when:

| Condition | Uncertainty message |
|---|---|
| Agreement score < 0.3 | "Low signal agreement. Only N of M signals contributed. Localisation may be unreliable." |
| No embedding signal available | "Embedding retrieval unavailable. Results rely on keyword and graph signals only." |
| Graph index stale | "Graph index is stale (last indexed: <ts>). Candidates may miss recent changes." |
| Budget exceeded | "Context exceeds recommended 6-10 file budget. Candidates beyond 10 have lower confidence." |
| All stack trace frames unresolved | "No stack trace frames could be resolved to graph nodes. Localisation is speculative." |
| Memory hint rejected | "Memory hints were filtered by the misalignment guard. Trajectory data not used." |
| SARIF run stale | "Most recent SARIF run predates current graph snapshot. SARIF prior may not reflect current code." |
| Cross-language expansion unavailable | "No interface plugins registered. Cross-language localisation is incomplete." |

### 16.3 Confidence From Uncertainty

Uncertainty conditions downgrade the localisation confidence:

- No uncertainty conditions → confidence from agreement score applies.
- One or more `warning`-class conditions → downgrade one level.
- Any `error`-class condition (stale graph, all frames unresolved) → confidence capped at `heuristic`.

### 16.4 Uncertainty Tests

Required tests:

- Low agreement score → uncertainty message attached.
- Stale graph → confidence capped at `heuristic`.
- Budget exceeded → uncertainty note.
- No uncertainty conditions → clean result.

---

## 17. `get_relevant_files` MCP Tool

### 17.1 Purpose

`get_relevant_files` is the externally-callable MCP tool that runs the full fault localisation pipeline and returns a ranked candidate list.

### 17.2 Tool Input

```text
get_relevant_files input
  issue_text : str
  repos : list[str] | None         # None = all registered repos
  failing_tests : list[str] | None # Test node IDs or names for SBFL
  coverage_path : str | None       # Path to coverage report
  max_files : int | None           # Default 8
  include_symbols : bool | None    # Default False (file-level only)
  snapshot : str | None
  use_embedding : bool | None      # Default True if available
  budget : dict | None
```

### 17.3 Tool Output

```text
get_relevant_files output
  ranked_files : list[CandidateFile]
  ranked_symbols : list[CandidateSymbol] | None
  agreement_score : float
  confidence : str
  uncertainty : str | None
  signals_used : list[str]
  signals_missing : list[str]
  context_bundle_ref : ArtifactRef  # Reference to stored ContextBundle
  run_event_ids : list[str]
  snapshot_ids : dict[str, str]
```

### 17.4 Tool Behavior

1. Normalize issue text.
2. Run all available retrieval signals in parallel (keyword, embedding, SARIF, blame, graph, SBFL, memory stub).
3. Merge with ranking policy.
4. Assemble bounded context bundle.
5. Compute agreement score and uncertainty.
6. If `include_symbols=True`, narrow to symbol level and generate reasoning chains.
7. Store context bundle as artefact.
8. Return ranked candidates.

### 17.5 Parallelism

Keyword, SARIF, blame, and graph retrieval are deterministic and may run in parallel. Embedding retrieval may be async if the adapter supports it. SBFL runs only when coverage is available. All signals are awaited before merging.

### 17.6 Task Support

`get_relevant_files` is task-capable for large repos or when embedding retrieval is slow.

### 17.7 Permission Descriptor

```text
required_mode : read/search
path_scope : registered repos
network_requirement : conditional (embedding adapter may require model endpoint)
side_effect_class : writes_vector_cache, read_only_graph
approval_requirement : not required
```

### 17.8 `get_relevant_files` Tests

Required tests:

- Issue with stack trace → stack trace file ranked first.
- Issue without stack trace → keyword + embedding retrieval used.
- SARIF prior applied for security-related issue text.
- Blame prior applied for regression-style issue text.
- Graph expansion adds callers of top candidates.
- SBFL signal applied when coverage provided.
- `include_symbols=True` → symbol-level candidates returned.
- Embedding unavailable → keyword-only result with uncertainty note.
- Task creation for large repo.

---

## 18. Private `investigate` Skill Template Foundation

### 18.1 Purpose

`investigate.py` lays the foundation for the private `investigate` skill template that Phase 13 `run_issue_resolution` will use. Phase 9 delivers the data flow and prompt template; Phase 13 integrates it into the full repair orchestration.

### 18.2 What Phase 9 Delivers

- `InvestigateInput` and `InvestigateOutput` models.
- The internal orchestration of `get_relevant_files` → `get_graph_slice` → symbol-summary retrieval → SARIF/build/test evidence → reasoning chain.
- The prompt template stub (Markdown, stored in `mcp_server/prompts/`).
- Provenance recording for each step.

### 18.3 What Phase 13 Adds

- Integration with the repair workflow.
- Run-record lifecycle (create run, append events, close).
- Monitor hooks (loop detection, budget hard-stop).
- DryRUN prediction.

### 18.4 `InvestigateInput`

```text
InvestigateInput
  issue_text : str
  repos : list[str] | None
  budget : InvestigateBudget
  snapshot : str | None
  prior_localisation : LocalisationResult | None   # From prior attempt or memory

InvestigateBudget
  max_files : int             # Default 8
  max_symbols_per_file : int  # Default 5
  max_context_tokens : int    # Default 8000
  use_embedding : bool        # Default True
  enable_cross_language : bool  # Default True
  enable_sbfl : bool          # Default False
```

### 18.5 `InvestigateOutput`

```text
InvestigateOutput
  localisation_result : LocalisationResult
  context_bundle : ContextBundle
  reasoning_chains : list[CandidateReasoningEntry]
  memory_hints_used : list[str]        # Empty until Phase 17
  memory_hints_rejected : list[str]    # Empty until Phase 17
  cross_language_hops : list[TraversalHop]
  provenance : InvestigateProvenance

InvestigateProvenance
  signals_run : list[str]
  signals_available : list[str]
  embedding_model : str | None
  graph_snapshot_ids : dict[str, str]
  sarif_run_ids : list[str]
  blame_freshness : str
  sbfl_available : bool
  memory_phase : str   # "stub" in Phase 9

CandidateReasoningEntry
  candidate_id : str
  file_path : str
  reasoning_chain : str
  derivation : str      # deterministic, llm
  evidence_citations : list[str]
```

### 18.6 Private Prompt Template Stub

`mcp_server/prompts/investigate.md` (private template, not exposed in `prompts/list`):

```markdown
# Investigate: Fault Localisation

## Context
- Issue: {issue_text_normalized}
- Repos: {repos}
- Budget: {budget}

## Pre-assembled evidence
{context_bundle_summary}

## Candidate ranking
{ranked_candidates_with_signals}

## Instructions
For each candidate:
1. State the signal evidence linking the issue to this candidate.
2. State any graph/static evidence (calls, data-flow, SARIF, blame).
3. State counter-evidence if present.
4. Produce a 2-3 sentence reasoning chain.

After reasoning through each candidate, produce a final ranked list
with the most likely root-cause location first.

## Constraints
- Only cite file paths and symbol names from the pre-assembled evidence.
- Mark localisation as uncertain if fewer than {min_agreement_signals} signals agree.
- Do not expand context beyond the pre-assembled bundle.
```

### 18.7 Investigate Tests

Required tests:

- `InvestigateInput` validates.
- `InvestigateOutput` validates.
- Provenance populated correctly.
- Memory phase recorded as "stub" in Phase 9.
- Cross-language hops included when plugins registered.
- Prompt template renders with fixture data.

---

## 19. Memory Hint Integration Interface

### 19.1 Purpose

`memory_stub.py` provides the interface that Phase 17 will implement for memory retrieval. Phase 9 registers the stub with zero weight so the pipeline compiles and tests pass without Phase 17.

### 19.2 `MemoryHintInterface`

```text
MemoryHintInterface (abstract)
  retrieve_fl_hints(
    issue_text: IssueText,
    max_hints: int,
  ) -> MemoryHintResult

MemoryHintResult
  hints_used : list[MemoryHint]
  hints_rejected : list[MemoryHint]
  misalignment_guard_applied : bool

MemoryHint
  hint_id : str
  issue_class : str
  fl_class : str
  suggested_files : list[str]
  suggested_symbols : list[str]
  utility_score : float
  source_run_id : str
```

### 19.3 Stub Behavior

`MemoryHintStub` implements `MemoryHintInterface`:

- `retrieve_fl_hints` always returns empty `hints_used` and empty `hints_rejected`.
- Signal weight for `MEMORY_HINT` is zero when stub is active.
- Stub is registered by default; Phase 17 replaces it with a real implementation.

### 19.4 Memory Stub Tests

Required tests:

- Stub returns empty result.
- `MEMORY_HINT` weight is zero when stub active.
- Pipeline compiles and produces `LocalisationResult` with empty memory hints.

---

## 20. Test Plan

### 20.1 Issue Normalizer Tests

Required:

- All five normalization stages on fixture issues.
- Stack trace extraction (Python, TS, C++).
- Entity extraction (symbols, files, errors).
- Language hint detection.
- Missing sections return `None`.

### 20.2 Retrieval Signal Tests

Required:

- Keyword: exact match, fuzzy match, stack trace bonus, multi-repo.
- Embedding: null adapter, vector similarity, batch embed.
- SARIF prior: error match, symbol match, stale run diagnostic.
- Blame prior: commit message match, churn score, stale records.
- Graph expansion: callers, tests, cross-language.
- SBFL: Ochiai formula, LCOV parse, Cobertura parse, unavailable signal.

### 20.3 Vector Cache Tests

Required:

- Store, retrieve, invalidate by file, invalidate by repo.
- Stale `git_sha` returns `None`.
- Purge expired entries.

### 20.4 Context Assembler Tests

Required:

- Top-8 files → bundle with 8 entries.
- Over-budget note.
- Graph slice, summaries, alerts, blame per file.
- Exact span for stack frame line.
- Full file content not included.

### 20.5 Ranking Tests

Required:

- Multi-signal agreement → higher score.
- Missing signal weight redistribution.
- Generated file ranked lower.
- Agreement score and confidence mapping.

### 20.6 Uncertainty Tests

Required:

- Low agreement → uncertainty message.
- Stale graph → confidence capped.
- Budget exceeded → note.

### 20.7 Reasoning Tests

Required:

- Deterministic chain from signals.
- Hallucinated citation stripped.
- Ungrounded chain → confidence downgrade.

### 20.8 MCP Tool Tests

Required:

- `get_relevant_files` with stack trace issue → stack trace file first.
- `get_relevant_files` without stack trace → keyword/embedding used.
- Graph expansion applied.
- SBFL signal applied with coverage.
- Task creation for large repo.
- Uncertainty note for low agreement.

### 20.9 Investigate Template Tests

Required:

- `InvestigateInput` and `InvestigateOutput` validate.
- Prompt template renders.
- Provenance populated.
- Memory stub returns empty hints.

### 20.10 Integration Tests

Required:

- Full pipeline on `fl_python_repo` fixture.
- Correct file in top-3 for each fixture issue.
- Agreement score computed correctly.
- Context bundle stored as artefact.

### 20.11 Regression Tests

Required:

- `get_relevant_files` tool descriptor snapshot.
- Default signal weights snapshot.
- Ranking policy snapshot.

---

## 21. Work Packages

### P9.1 Issue Text Normalizer

Build:

- `IssueText` model and `StackFrame` model.
- Five normalization stages.
- Entity extraction.
- Language hint detection.

Deliverables:

- `fl/issue.py`
- Issue fixture files.
- Issue normalizer tests.

Acceptance:

- All fixture issues parse without error. Stack traces extracted correctly.

### P9.2 Keyword Retrieval

Build:

- BM25-style scoring against graph index.
- Stack trace bonus.
- Multi-repo search.

Deliverables:

- `fl/keyword_retrieval.py`
- Keyword retrieval tests.

Acceptance:

- Exact symbol name in issue → correct file ranked first.

### P9.3 Embedding Interface And Vector Cache

Build:

- `EmbeddingInterface` abstract class.
- `EmbeddingVector` model.
- `NullAdapter`.
- `VectorCache` with `git_sha`-based invalidation.
- Schema migration for vector cache table.

Deliverables:

- `fl/embedding_interface.py`, `fl/vector_cache.py`
- `fl/embedding_adapters/null_adapter.py`
- Embedding and cache tests.

Acceptance:

- Null adapter runs pipeline. Cache invalidation on `git_sha` change.

### P9.4 SARIF Proximity Prior

Build:

- Error string, symbol, CWE, and rule-family matching.
- Severity-weighted score.
- Alert currency check.

Deliverables:

- `fl/sarif_prior.py`
- SARIF prior tests.

Acceptance:

- Error string match → correct file scored high.

### P9.5 Blame And History Prior

Build:

- Commit message keyword matching.
- Churn scoring.
- Recency decay.

Deliverables:

- `fl/blame_prior.py`
- Blame prior tests.

Acceptance:

- Commit mentioning issue keyword → related file scored higher.

### P9.6 Graph-Neighbour Expansion

Build:

- Hop-based graph expansion.
- Cross-language expansion via Phase 7.
- Hop decay and expansion limits.

Deliverables:

- `fl/graph_expansion.py`
- Graph expansion tests.

Acceptance:

- Caller of top candidate added as expansion. Cross-language expansion works with Phase 7 fixture.

### P9.7 SBFL/Ochiai Feature

Build:

- Ochiai formula.
- LCOV and Cobertura parsers.
- Availability check.

Deliverables:

- `fl/sbfl.py`
- SBFL tests.

Acceptance:

- Ochiai score computed for fixture coverage. Unavailable signal produces diagnostic.

### P9.8 Bounded Context Assembler

Build:

- Per-file graph slice, summary, SARIF, blame, and span assembly.
- 6–10 file budget enforcement.
- Over-budget uncertainty note.
- `ContextBundle` model.

Deliverables:

- `fl/context_assembler.py`
- Context assembler tests.

Acceptance:

- Budget enforced. Exact spans included only for stack frame lines.

### P9.9 Ranking Policy, Uncertainty Model, And Reasoning Scaffold

Build:

- Weighted linear combination ranking.
- Signal weight redistribution for missing signals.
- Agreement score.
- Uncertainty conditions and confidence downgrade.
- Deterministic reasoning chain.
- LLM reasoning chain validation.

Deliverables:

- `fl/ranking.py`, `fl/uncertainty.py`, `fl/reasoning.py`
- Ranking, uncertainty, and reasoning tests.

Acceptance:

- Multi-signal agreement produces higher confidence. Low agreement → uncertainty note.

### P9.10 `get_relevant_files` Tool, Investigate Foundation, And Memory Stub

Build:

- `LocalisationResult` model.
- `get_relevant_files` tool handler.
- `investigate.py` foundation with `InvestigateInput`/`InvestigateOutput`.
- Private `investigate` prompt template stub.
- `memory_stub.py`.
- Integration tests.

Deliverables:

- `mcp_server/tools/fl.py`
- `fl/localisation.py`, `fl/investigate.py`, `fl/memory_stub.py`
- `mcp_server/prompts/investigate.md`
- Tool, investigate, and integration tests.

Acceptance:

- `get_relevant_files` returns ranked files for fixture issues. Top-1 recall ≥ 50% on fixture set.

---

## 22. Suggested Implementation Order

Recommended order:

1. Issue text normalizer and fixture issue files.
2. `IssueText` model and `CandidateFile`/`CandidateSignal` models.
3. Keyword retrieval (no external dependencies; validates the index query path).
4. Ranking policy with single-signal support.
5. Bounded context assembler (establishes the output contract).
6. `get_relevant_files` tool with keyword-only path.
7. Embedding interface abstract class and null adapter.
8. Vector cache with schema migration.
9. SARIF proximity prior.
10. Blame and history prior.
11. Graph-neighbour expansion.
12. SBFL module.
13. Multi-signal ranking policy extension.
14. Agreement score and uncertainty model.
15. RGFL reasoning chain scaffold.
16. `InvestigateInput`/`InvestigateOutput` models.
17. `investigate.py` foundation.
18. Memory hint stub.
19. Private `investigate` prompt template stub.
20. Integration tests and regression harness.

Reasoning:

- Keyword retrieval first because it has no external dependencies and validates the graph query path.
- Ranking policy before all signals so each signal can be independently plugged in.
- Context assembler early to establish the output contract that Phase 13 depends on.
- Embedding interface before the embedding retrieval path, null adapter allows immediate testing.
- SARIF, blame, and graph expansion independently after the base pipeline is proven.
- SBFL last among signals because it requires coverage data infrastructure.
- Investigate foundation after all signals because it orchestrates them.

---

## 23. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 9 |
|---|---|
| Phase 10 - Evaluation harness | `get_relevant_files` as the FL evaluation target; `LocalisationResult` for top-1/top-3/top-N FL metrics; agreement score as a reliability metric; `investigate` output as T2 nightly regression input |
| Phase 12 - SAST repair | `get_relevant_files` to locate files containing the target SARIF alert's context; SARIF proximity prior already applied |
| Phase 13 - Bug-resolve | `InvestigateInput`/`InvestigateOutput` models; `investigate.py` orchestration; `ContextBundle` as the repair context; `ranked_symbols` as the repair starting point |
| Phase 14 - Implementation-check | `get_relevant_files` as the initial file candidate source for clause-to-code grounding |
| Phase 15 - Blast radius | `ranked_symbols` as the blast-radius starting set; graph-expansion output as neighbours |
| Phase 16 - Dynamic traces | `ContextBundle.exact_spans` as the scope filter for `capture_trace`; ranked suspects as trace entry points |
| Phase 17 - Memory | `MemoryHintInterface` stub replaced by real implementation; `IssueText` as the memory retrieval key; `LocalisationResult` stored as trajectory FL decision |
| Phase 18 - Release gates | FL top-1/top-3 metrics from T2 harness; resolve-rate conditioned on correct FL; embedding model calibration inputs |

---

## 24. Exit Criteria Mapping

Source Phase 9 exit criterion:

- `get_relevant_files(issue_text)` returns ranked files with evidence.

Concrete acceptance:

- `get_relevant_files` on fixture `python_null_deref.jsonl` returns a `ranked_files` list with at least one entry.
- Each entry carries `signals`, `combined_score`, and `confidence`.
- The correct file appears in top-3 for all fixture issues where keyword + graph evidence is available.

Source Phase 9 exit criterion:

- `investigate` returns suspect symbols/files with reasoning and uncertainty.

Concrete acceptance:

- `investigate(issue_text)` returns an `InvestigateOutput` with `ranked_symbols` non-empty for fixture issues.
- Each symbol carries `reasoning_chain` (deterministic or LLM).
- `uncertainty` field is populated when agreement score is low.
- `InvestigateProvenance` records all signals run.

Source Phase 9 exit criterion:

- Retrieved summaries, memory hints, graph slices, and exact code spans are all separately attributed.

Concrete acceptance:

- `ContextBundle` contains `graph_slices`, `symbol_summaries`, `exact_spans`, and `build_test_evidence` as separate fields.
- Each item carries `confidence` and `source` attribution.
- Memory hints field is present (empty in Phase 9 due to stub).
- No field contains full file content.

Source Phase 9 exit criterion:

- Low agreement between semantic retrieval and graph/static evidence produces an uncertain localisation.

Concrete acceptance:

- Fixture issue where only the keyword signal fires: `agreement_score < 0.3` and `uncertainty` message is present.
- `confidence` is `heuristic` for that result.

---

## 25. Definition Of Done

Phase 9 is done when:

- Issue text normalizer handles Python, TS/JS, and C++ stack traces plus all fixture issue formats.
- Keyword retrieval produces ranked candidates against the fixture graph.
- Embedding interface abstract class and null adapter allow pipeline testing without a model.
- Vector cache stores and invalidates vectors by `git_sha`.
- SARIF proximity prior scores files by alert matches.
- Blame prior scores files by commit message and churn.
- Graph-neighbour expansion adds callers, tests, and cross-language peers.
- SBFL module computes Ochiai from LCOV/Cobertura where available.
- Context assembler produces bounded bundles of 6–10 files with graph slices, summaries, SARIF, and blame.
- Ranking policy combines signals with configurable weights.
- Agreement score maps to confidence level.
- Uncertainty conditions attach explanatory notes.
- RGFL deterministic reasoning chain assembled from signal evidence.
- `get_relevant_files` MCP tool returns ranked candidates with evidence.
- `InvestigateInput`, `InvestigateOutput`, and `InvestigateProvenance` models validate.
- `investigate.py` orchestrates the full pipeline from issue text to context bundle.
- Memory hint stub contributes zero weight.
- Private `investigate` prompt template stub renders with fixture data.
- All Phase 3/4/5/6/7/8 tests continue to pass.

---

## 26. Risks, Mitigations, Completion Report, And Minimal First Slice

### 26.1 Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Embedding model not available in CI | Embedding signal always zero; FL quality lower | Null adapter gracefully skips embedding; keyword + graph signals still provide useful ranking; CI test with null adapter; document model setup |
| Stack trace file paths not matching repo-relative graph node paths | Stack trace bonus never fires | Normalize stack trace paths using the same repo-root-stripping logic as Phase 6 URI resolution; test with both absolute and relative stack trace paths |
| Keyword retrieval returns too many low-quality candidates | Context assembler overwhelmed | Minimum score threshold (default 0.05) filters weak candidates; BM25 score caps at top-50 before merging |
| Graph-neighbour expansion adds irrelevant files (e.g., widely-imported utilities) | High-churn utility files pollute ranking | Expansion score decays by hop count; files imported by >50% of all files receive zero expansion weight (hub dampening) |
| SARIF prior stale for long-running repos | Wrong prior applied | Alert currency check enforced; stale SARIF emits `SARIF_STALE` diagnostic and contributes zero weight |
| SBFL coverage data out of sync with current code | False suspiciousness scores | Coverage linked to `git_sha`; stale coverage (SHA mismatch) contributes zero weight |
| 6-10 file budget too small for some issues | Correct file missed | Budget is a configurable soft default; `max_files=20` hard maximum with uncertainty note; measure recall@K in Phase 10 eval |
| Agreement score threshold miscalibrated | Uncertain localisations when actually correct, or vice versa | Threshold configurable; Phase 10 eval will measure FL accuracy vs. agreement score correlation and recalibrate |
| Memory hint stub weight zero blocks memory integration | Phase 17 memory not effective | Memory weight is configurable; default zero until Phase 17 proves benefit ≥3 pp; Phase 17 sets the weight after validation |
| LLM reasoning chain hallucination | Wrong file names cited | Post-generation validation strips non-existent citations; hallucination logged as diagnostic; confidence downgraded |

### 26.2 Completion Report Template

When Phase 9 implementation is complete, report:

```text
Phase 9 completion report

Implemented:
- Issue text normalizer (5 stages):
- Keyword retrieval:
- Embedding interface and null adapter:
- Vector cache with git_sha invalidation:
- SARIF proximity prior:
- Blame and history prior:
- Graph-neighbour expansion:
- SBFL/Ochiai module:
- Bounded context assembler:
- Ranking policy (signal weighting):
- Agreement score and uncertainty model:
- RGFL reasoning chain scaffold:
- LocalisationResult and ContextBundle models:
- get_relevant_files MCP tool:
- investigate.py foundation:
- Memory hint stub:
- Private investigate prompt template stub:

Verification:
- Issue normalizer tests (Python/TS/C++ stacks):
- Keyword retrieval tests:
- Vector cache tests:
- SARIF prior tests:
- Blame prior tests:
- Graph expansion tests:
- SBFL tests:
- Context assembler tests:
- Ranking tests:
- Uncertainty model tests:
- Reasoning chain tests:
- get_relevant_files tool tests:
- investigate foundation tests:
- Integration tests (fixture issues):
- Local verify command:

Exit criteria:
- get_relevant_files returns ranked files with evidence:
- investigate returns suspects with reasoning and uncertainty:
- Summaries, memory hints, slices, spans separately attributed:
- Low agreement → uncertain localisation:
- Phase 3-8 tests still pass:

Top-1 recall on fixture set: __/__ issues correct file in top-1
Top-3 recall on fixture set: __/__ issues correct file in top-3

Known limitations:
-

Follow-up for Phase 10 (Evaluation Harness):
-
```

### 26.3 Minimal First Slice Within Phase 9

If Phase 9 needs to be split further, implement this first:

1. Issue text normalizer with Python stack trace extraction.
2. `IssueText`, `CandidateFile`, `CandidateSignal` models.
3. Keyword retrieval with stack trace bonus.
4. Bounded context assembler (file-level, no symbol narrowing).
5. Single-signal ranking policy.
6. `LocalisationResult` model.
7. `get_relevant_files` tool (keyword-only path).
8. Integration test: correct file in top-3 for Python fixture issues.

This minimal slice validates the data model and graph query path without embedding retrieval. SARIF, blame, SBFL, and graph expansion can be added incrementally as subsequent slices. The embedding interface and vector cache land in the second slice when the base pipeline is proven.
