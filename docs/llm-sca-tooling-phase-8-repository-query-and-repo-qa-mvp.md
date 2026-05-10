# LLM-SCA Tooling Phase 8 Implementation Plan: Repository Query and Repo-QA MVP

> Date: 2026-05-09  
> Repository name: `evidence-sca`  
> Source plan: `llm-sca-tooling-implementation-plan.md`  
> Source architecture: `llm-sca-tooling-architecture.md`  
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 8 - Repository Query and Repo-QA MVP  
> Primary objective: provide evidence-cited repository question-answering and graph behaviour tracing by implementing a question classifier (`file-loc`, `symbol-loc`, `behaviour-trace`, `contract-check`, `other`), deterministic file and symbol lookup, a graph-path answer builder, behaviour-trace graph traversal, interface-contract lookup, a fully typed evidence assembler, LLM synthesis behind a typed boundary, confidence rules separated by question class, and the `classify_repo_question`, `answer_repo_question`, `get_interface_contract`, and `git_blame_chain` MCP tools.

---

## 1. Phase Summary

Phases 3–7 built a typed repository graph, a SARIF evidence layer, and a cross-language interface plugin system. Phase 8 answers natural-language questions about that graph. A developer asking "where is login validation implemented?" or "what happens when the frontend calls this endpoint?" should receive a cited, structured answer grounded in graph facts rather than a free-form prose guess.

The central rule for this phase is:

```text
No answer may carry higher confidence than its weakest supporting evidence.
File-location answers that are graph-confirmed may reach parser confidence.
Behaviour-tracing answers must remain supporting evidence until the
graph-augmented swe-qa / coreqa behaviour subset reaches the >=70% ship-gate.
LLM synthesis is a presentation layer. It cannot self-certify.
```

Phase 8 should implement:

- Question model and `QuestionClass` enum: `file-loc`, `symbol-loc`, `behaviour-trace`, `contract-check`, `other`.
- Question classifier: deterministic rules first, optional lightweight LLM fallback for ambiguous text.
- Deterministic file and symbol lookup against the Phase 2/3/5 graph index.
- Graph-path answer builder for multi-hop traversal evidence.
- Behaviour-trace traversal: natural-language intent mapped to graph query, returning graph paths or `unknown`.
- Interface-contract lookup wrapping Phase 7 `InterfaceRecord` retrieval.
- Git blame chain resource and tool, graduating from Phase 3 blame-chain records to a full MCP tool.
- LLM answer synthesis behind a typed evidence interface.
- Evidence assembler with per-question-class confidence rules.
- Typed answer model carrying evidence citations, graph node references, and uncertainty.
- `classify_repo_question` MCP tool.
- `answer_repo_question` MCP tool.
- `get_interface_contract` MCP tool (thin typed wrapper over Phase 7 interface resources).
- `git_blame_chain` MCP tool (upgrading the Phase 3 blame records and Phase 4 resource to a first-class tool).
- Answer quality gates and ship thresholds per question class.

### Architecture Coverage

Phase 8 covers:

- F3 repo-QA and behaviour tracing.
- `classify_repo_question` MCP tool.
- `answer_repo_question` MCP tool.
- `get_interface_contract` MCP tool.
- `git_blame_chain` MCP tool.
- `code-intelligence://blame/{repo}/{file_path}` resource (graduating from Phase 3/4 backing data to a first-class resource handler with subscription support).

### Inherited Paper Anchors

Use these anchors in Phase 8 issues, ADRs, answer quality notes, and benchmark reports:

- `repo-path-retrieval-llm`
- `swd-bench`
- `swe-qa`
- `coreqa`
- `beyond-code-snippets`
- `repochat`
- `repograph`
- `codexgraph`
- `hafixagent`

Adjacent anchors useful for confidence and evaluation notes:

- `arise`
- `locagent`
- `rig`
- `logiclens`
- `swe-qa-pro`

## Technology Stack

| Library / Tool | PyPI package | Version | Purpose in this phase |
|---|---|---|---|
| markdown-it-py | `markdown-it-py` | >=3.0 | CommonMark-compliant parsing of Markdown spec and documentation files during question answering; used for spec document ingestion and structural token extraction |
| orjson | `orjson` | >=3.10 | JSON payload serialization for `answer_repo_question` response objects and evidence citation bundles |
| NetworkX | `networkx` | >=3.3 | Graph path traversal for behaviour-trace answers; shortest-path and multi-hop neighbour queries over the Phase 2/3/5/7 graph |
| Pydantic v2 | `pydantic` | >=2.0 (`extra="forbid"`) | `RepoQuestion`, `QuestionClass`, `AnswerEvidence`, `AnswerModel` typed models; `model_json_schema()` for schema export; no hand-written `.schema.json` |

Notes:

- LLM answer synthesis operates **behind a typed evidence interface**: the evidence assembler produces a fully typed `AnswerEvidence` bundle, which is passed to the LLM synthesis layer as structured input. The LLM cannot self-certify confidence — confidence is computed from the weakest evidence node in the bundle.
- `markdown-it-py` handles all Markdown document parsing (spec files, README files, inline documentation). It is not used for code parsing; code structure comes from the Phase 3/5 AST indexers.
- NetworkX graph traversal is read-only in this phase; no new graph edges are written by the QA layer.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 8 depends on:

- Phase 1 schemas:
  - Graph node types: `file`, `module`, `class`, `function`, `method`, `variable`, `type`, `interface`, `document`, `design_clause`, `idl_interface`, `http_route`, `websocket_event`.
  - Graph edge types: `contains`, `imports`, `calls`, `dataflow`, `tests`, `documents`, `implements`, `exposes`, `consumes`, `ffi`, `warned_by`.
  - Provenance, confidence, and derivation enums.
  - Common verdict values including `unknown`.
- Phase 2 stores:
  - Repository registry and snapshot ledger.
  - Graph store with fetch-by-ID, fetch-by-file/span, fetch-by-type, and neighbour queries.
  - Artefact registry.
- Phase 3/5 indexing outputs:
  - File nodes per repo-relative path.
  - Symbol nodes (class, function, method) with file/span provenance.
  - Import and call edges.
  - Blame-chain records collected by Phase 3 blame-chain collector.
  - Build and test evidence nodes.
  - Symbol summary cache.
- Phase 6 SARIF:
  - `sast_rule` and `sarif_alert` nodes linked via `warned_by` edges (used in contract-check answers).
- Phase 7 plugins:
  - `InterfaceRecord` and `InterfaceOperation` models from plugin registry.
  - `http_route`, `websocket_event`, `idl_interface` graph nodes.
  - `exposes`, `consumes`, `implements`, `ffi` graph edges.
  - `trace_cross_language` traversal engine.
- Phase 4 MCP:
  - Tool registry and permission descriptor model.
  - Telemetry and run event infrastructure.
  - `code-intelligence://blame/{repo}/{file_path}` resource backing store (Phase 3 records).

### Phase Outputs

Phase 8 should produce:

- Question model, `QuestionClass` enum, and question normalizer.
- Question classifier with deterministic rules and optional LLM fallback.
- Deterministic file lookup and symbol lookup against graph store.
- Graph-path answer builder.
- Behaviour-trace graph traversal module.
- Interface-contract lookup module.
- LLM synthesis typed interface and adapter.
- Evidence assembler.
- Per-question-class confidence rules.
- Typed answer model with evidence citations.
- `classify_repo_question` MCP tool and tests.
- `answer_repo_question` MCP tool and tests.
- `get_interface_contract` MCP tool and tests.
- `git_blame_chain` MCP tool (graduating from Phase 3/4) and tests.
- `code-intelligence://blame/{repo}/{file_path}` resource handler with subscription support.
- Answer quality gate configuration and ship threshold checks.
- QA fixture cases for each question class.

### Non-Goals

Do not implement these in Phase 8:

- Fault localisation ranking. That is Phase 9.
- Semantic embedding-based file retrieval (`get_relevant_files`). That is Phase 9.
- Implementation-check workflow. That is Phase 14.
- Bug-resolve workflow. That is Phase 13.
- Patch review. That is Phase 11.
- Training or fine-tuning of the `repo-path-retrieval-llm`-style model. That is Phase 18.
- Calibrated stage-7 aggregation. That is Phase 14/18.
- Dynamic trace capture. That is Phase 16.
- Full benchmark runner. That is Phase 10.

Phase 8 builds the QA infrastructure. It does not build the embedding retriever (Phase 9), the repair workflow (Phase 13), or the calibration machinery (Phase 18).

---

## 3. Recommended File Layout

```text
src/evidence_sca/
  qa/
    __init__.py
    question.py
    classifier.py
    lookup.py
    graph_query.py
    behaviour_trace.py
    interface_lookup.py
    blame.py
    evidence_assembler.py
    confidence.py
    answer.py
    synthesis.py
    ship_gate.py

  mcp_server/tools/
    qa.py
    blame.py

  mcp_server/resources/
    blame.py

tests/
  qa/
    fixtures/
      questions/
        file_loc_cases.jsonl
        symbol_loc_cases.jsonl
        behaviour_trace_cases.jsonl
        contract_check_cases.jsonl
        other_cases.jsonl
        edge_cases.jsonl
      repos/
        qa_python_repo/
          src/
          tests/
          README.md
    test_question.py
    test_classifier.py
    test_lookup.py
    test_graph_query.py
    test_behaviour_trace.py
    test_interface_lookup.py
    test_blame.py
    test_evidence_assembler.py
    test_confidence.py
    test_answer.py
    test_synthesis.py
    test_ship_gate.py
    test_classify_repo_question.py
    test_answer_repo_question.py
    test_get_interface_contract.py
    test_blame_tool.py
    test_blame_resource.py
    test_integration.py
```

---

## 4. Question Model And Question Class

### 4.1 Purpose

A `RepoQuestion` represents a normalized, repo-scoped natural-language question about a codebase. Normalization extracts intent structure before classification.

### 4.2 `QuestionClass` Enum

```text
QuestionClass
  FILE_LOC         # "Where is X implemented/defined/located?"
                   # → deterministic file/symbol lookup + graph confirmation
  SYMBOL_LOC       # "Which function/class/method does X?"
                   # → symbol-name graph lookup + interface link expansion
  BEHAVIOUR_TRACE  # "What happens when...? / How does X flow?"
                   # → NL-to-graph traversal + cross-language trace
  CONTRACT_CHECK   # "Is X enforced/satisfied? Where is this clause checked?"
                   # → doc/spec node binding + predicate/SARIF evidence
  OTHER            # Everything else; returned with low confidence
```

### 4.3 `RepoQuestion` Model

```text
RepoQuestion
  question_id : str
  raw_text : str
  normalized_text : str
  repos : list[str] | None
  context : str | None     # Additional prose context supplied by the caller
  snapshot_hint : str | None
  submitted_ts : str
```

### 4.4 Question Normalization

`question.py` applies normalization before classification:

- Lowercase and strip excess whitespace.
- Remove filler phrases: "can you tell me", "I was wondering", "please help me".
- Extract explicit code tokens: quoted identifiers, CamelCase tokens, snake_case tokens.
- Extract repo hints: `in repo X`, `for service Y`.
- Extract file hints: path-like tokens, file extensions.
- Preserve the normalized form separately from the raw text.

Rules:

- Normalization is deterministic.
- Raw text is always preserved alongside the normalized form.
- Normalization must not alter code tokens or quoted strings.

### 4.5 Model Tests

Required tests:

- `RepoQuestion` round-trips through serialization.
- Normalization strips filler phrases.
- Normalization preserves code tokens.
- File hints extracted from path-like tokens.

---

## 5. Question Classifier

### 5.1 Purpose

`classifier.py` assigns a `QuestionClass` to a `RepoQuestion`. Classification must be fast, deterministic where possible, and auditable.

### 5.2 Classifier Architecture

The classifier runs two stages:

**Stage 1 — Deterministic rule classifier** (always runs first):
- Applies a priority-ordered rule set.
- Rules are expressed as weighted pattern matches on normalized text.
- If a rule fires with sufficient weight, return the class without entering Stage 2.

**Stage 2 — Optional LLM fallback** (only when Stage 1 is ambiguous):
- Runs a small prompted LLM call with the normalized question text.
- LLM output is constrained to one of the five class labels.
- LLM fallback result carries `derivation=llm`, `confidence=heuristic`.
- Stage 2 is disabled by default in non-interactive or budget-constrained contexts.

### 5.3 Deterministic Rule Set

Priority-ordered rules:

```text
FILE_LOC indicators:
  - "where is", "where can I find", "which file", "what file", "in which file"
  - "where does X live", "where is X defined", "what path"
  - "find the file", "locate the file"
  - Code token followed by "implemented in", "defined in", "found in"

SYMBOL_LOC indicators:
  - "which function", "which method", "which class", "which module"
  - "what function", "what method", "what class"
  - "who handles", "what handles", "what implements"
  - "which code", "find the function", "find the class"

BEHAVIOUR_TRACE indicators:
  - "what happens when", "what happens if", "how does X work"
  - "trace the flow", "follow the call", "execution flow"
  - "when X is called", "what is the path from", "walk me through"
  - "how does a request reach", "end-to-end flow"

CONTRACT_CHECK indicators:
  - "is X enforced", "is X satisfied", "does X comply"
  - "where is this requirement", "where is this spec clause"
  - "is there a check for", "how is X validated", "which predicate"
  - "does the code satisfy", "is the contract met"

OTHER fallback:
  - All questions not matched above
```

Rule weights: each matching indicator phrase increases the score for its class. The class with the highest aggregate score wins if the score exceeds the ambiguity threshold. Below the threshold, enter Stage 2 or return `OTHER` with `confidence=heuristic`.

### 5.4 Classification Result

```text
ClassificationResult
  question_id : str
  question_class : QuestionClass
  confidence : ConfidenceLevel
  derivation : str         # deterministic, llm_fallback
  matched_rules : list[str]
  score : float
  alternative_class : QuestionClass | None
  alternative_score : float | None
```

### 5.5 Classifier Tests

Required tests:

- "Where is login implemented?" → `FILE_LOC`.
- "Which function handles authentication?" → `SYMBOL_LOC`.
- "What happens when the user submits a form?" → `BEHAVIOUR_TRACE`.
- "Is the null check enforced for user IDs?" → `CONTRACT_CHECK`.
- "Tell me about the repo." → `OTHER`.
- Ambiguous question returns the highest-scoring class with `alternative_class`.
- Stage 2 (LLM fallback) disabled in budget-constrained mode.
- Classification result carries `derivation` and `matched_rules`.

---

## 6. Deterministic File And Symbol Lookup

### 6.1 Purpose

`lookup.py` provides fast, evidence-cited file and symbol lookup directly against the Phase 2 graph store. This is the primary answer path for `FILE_LOC` and `SYMBOL_LOC` questions. It does not call an LLM.

### 6.2 File Lookup

`FileLocLookup` searches the graph store for `file` nodes.

Lookup strategies (ordered by confidence):

1. **Exact path match**: question text contains a repo-relative path fragment. Query graph for file nodes with matching path suffix.
   - Confidence: `parser`.

2. **Module name match**: question text contains a Python module name or JS module name. Match `module` nodes and return their file paths.
   - Confidence: `parser`.

3. **Symbol-to-file inference**: if the question names a symbol, look up the symbol node and return its containing file.
   - Confidence: `parser` when symbol is found exactly.

4. **Keyword file-name match**: tokenize question text, match file base names (without extension) case-insensitively against `file` node names.
   - Confidence: `analyser`.

5. **Build evidence hint**: if question mentions "test", "test file", or "CI", return `ci_job` and `build_target` nodes.
   - Confidence: `heuristic`.

### 6.3 Symbol Lookup

`SymbolLocLookup` searches the graph store for symbol nodes.

Lookup strategies:

1. **Exact symbol name match**: query for `function`, `method`, `class` nodes with name exactly matching a code token in the question.
   - Confidence: `parser`.

2. **Qualified name match**: dotted paths like `UserService.validate` split into class + method query.
   - Confidence: `parser`.

3. **Case-insensitive fuzzy match**: match symbol names after lower-casing and removing underscores/camelCase word breaks.
   - Confidence: `analyser`.

4. **Interface link expansion**: if the matched symbol is a route handler, servant, or stub method, also return the connected `http_route`, `idl_interface`, or `websocket_event` node.
   - Confidence: same as the underlying symbol match.

### 6.4 `LookupResult`

```text
LookupResult
  question_class : QuestionClass
  matched_nodes : list[GraphNodeRef]
  lookup_strategy : str
  confidence : ConfidenceLevel
  diagnostics : list[str]

GraphNodeRef
  node_id : str
  node_type : str
  file_path : str | None
  span : Span | None
  symbol_path : str | None
  confidence : ConfidenceLevel
  source : str          # exact_path, module_name, symbol_to_file, keyword, ...
```

### 6.5 Lookup Tests

Required tests:

- "Where is `UserService.validate`?" → exact symbol match, parser confidence.
- "Find the file `auth/views.py`" → exact path match.
- "Which file contains login logic?" → keyword file-name match, analyser confidence.
- Question naming symbol in multiple repos → results from all repos with repo annotations.
- No match found → empty `matched_nodes`, `unknown` confidence.
- Module name resolution: "the `auth` module" → correct file node.

---

## 7. Graph-Path Answer Builder

### 7.1 Purpose

`graph_query.py` builds answers from graph traversal paths. This is used for `SYMBOL_LOC` answers where the evidence is a chain of graph edges, and for `CONTRACT_CHECK` answers where the link from doc node to code node is the answer.

### 7.2 `GraphPathBuilder`

```text
GraphPathBuilder
  graph_store : GraphStoreQuery

  build_path(
    start_node_id: str,
    end_node_id: str | None,
    edge_types: list[str],
    max_depth: int,
  ) -> list[GraphPath]

  build_ego_graph(
    node_id: str,
    edge_types: list[str],
    depth: int,
  ) -> GraphSlice

  find_document_links(
    node_id: str,
  ) -> list[DocumentLink]
```

### 7.3 `GraphPath`

```text
GraphPath
  path_id : str
  nodes : list[GraphNodeRef]
  edges : list[GraphEdgeRef]
  start_node_id : str
  end_node_id : str
  hop_count : int
  confidence : ConfidenceLevel  # min confidence across all edges in path
  snippet_refs : list[ArtifactRef]
```

### 7.4 `DocumentLink`

Document links connect `documents` edges from `document` or `design_clause` nodes to code symbol nodes.

```text
DocumentLink
  doc_node_id : str
  doc_file_path : str | None
  doc_span : Span | None
  code_node_id : str
  code_file_path : str
  code_span : Span | None
  edge_type : str     # documents, checks, satisfies, ...
  confidence : ConfidenceLevel
```

Used in `CONTRACT_CHECK` answers to show where a spec clause is bound to code.

### 7.5 Graph-Path Tests

Required tests:

- Path from caller to callee via `calls` edge.
- Ego-graph includes imports and calls at depth 1.
- Document link returned for `documents` edge.
- No path between disconnected nodes returns empty list.
- Confidence of path is minimum edge confidence along the path.

---

## 8. Behaviour-Trace Graph Traversal

### 8.1 Purpose

`behaviour_trace.py` translates a natural-language behaviour question into a bounded graph traversal and returns graph paths or `unknown` when the graph cannot support the answer.

This is the hardest question class. The architecture documents a 40–60% accuracy range on `swe-qa`/`coreqa` behaviour subsets before the ≥70% ship-gate is met. Phase 8 builds the traversal infrastructure but keeps answers at `heuristic` confidence until calibration is complete.

### 8.2 Intent Extraction

Before traversal, extract intent signals from the question:

```text
BehaviourIntent
  trigger_tokens : list[str]      # "user submits", "request arrives", "button clicked"
  target_tokens : list[str]       # "the response", "the database", "the C++ service"
  scope_tokens : list[str]        # "within the auth module", "across the API boundary"
  direction : str                 # forward (caller → callee), backward (callee → caller), bidirectional
```

Intent extraction is deterministic (token pattern matching). It is not an LLM call.

### 8.3 Traversal Plan

From the intent, build a `TraversalPlan`:

1. Resolve `trigger_tokens` to candidate start graph nodes via deterministic lookup.
2. Resolve `target_tokens` to candidate end graph nodes if identifiable.
3. Select edge types to follow based on scope: `calls`, `dataflow`, `imports`, `exposes`, `consumes`, `ffi`.
4. Invoke `CrossLanguageTraverser` from Phase 7 when cross-language intent is present.
5. Invoke `GraphPathBuilder` for same-language traversal.
6. Return graph paths ordered by shortest-hop-count, bounded by `max_hops`.

### 8.4 Returning `unknown`

Return `unknown` with explanation when:

- No start nodes are resolved from `trigger_tokens`.
- Start nodes are resolved but no path exists to any end node within `max_hops`.
- All found paths cross-language but no plugin is registered for the detected boundary.
- The traversal finds only stale or dirty-snapshot edges.
- Intent extraction produces zero start tokens.

`unknown` is a valid, first-class answer. It must carry a reason string.

### 8.5 Behaviour-Trace Confidence Cap

Behaviour-trace answers are capped at `heuristic` confidence regardless of graph path confidence, until the local `swe-qa`/`coreqa` behaviour-subset accuracy exceeds the configured ship threshold (default: 70%).

When the threshold is not met, the answer model must include:

```text
uncertainty = "Behaviour-tracing accuracy has not yet met the >=70% ship-gate.
               This answer is supporting evidence only and must not be used
               as a definitive verdict."
```

### 8.6 Behaviour-Trace Tests

Required tests:

- Trigger token resolved to start node, path found → graph paths returned.
- Trigger token with cross-language intent → `trace_cross_language` invoked.
- No start node resolved → `unknown` with reason.
- No path found within max_hops → `unknown`.
- Stale snapshot nodes → `unknown` with stale-snapshot reason.
- Confidence always capped at `heuristic`.
- `uncertainty` message present in all non-unknown results.

---

## 9. Interface-Contract Lookup

### 9.1 Purpose

`interface_lookup.py` retrieves `InterfaceRecord` objects from the Phase 7 plugin registry for `CONTRACT_CHECK` and `SYMBOL_LOC` questions that reference interface boundaries.

### 9.2 Lookup Paths

1. **By interface name**: match the question's code tokens against `InterfaceRecord.interface_name`.
2. **By symbol node**: if a matched symbol is linked to an interface via `exposes`, `consumes`, or `implements` edges, return the associated `InterfaceRecord`.
3. **By file path**: if the question references an IDL file, OpenAPI file, or known interface definition file, return all `InterfaceRecord` objects linked to that file.

### 9.3 `InterfaceContractResult`

```text
InterfaceContractResult
  interface_record : InterfaceRecord
  plugin_id : str
  interface_name : str
  matched_operations : list[InterfaceOperation]
  server_node_refs : list[GraphNodeRef]
  client_node_refs : list[GraphNodeRef]
  confidence : ConfidenceLevel
  lookup_path : str   # by_name, by_symbol, by_file
```

### 9.4 Interface Lookup Tests

Required tests:

- Name match returns correct `InterfaceRecord`.
- Symbol-linked interface lookup via `exposes` edge.
- File-path lookup for IDL file.
- Unknown interface name returns empty result.
- Multiple matching plugins return results from all.

---

## 10. Git Blame Chain Resource And Tool

### 10.1 Evolution From Phase 3

Phase 3 collected blame-chain records as part of the indexing pipeline. Phase 4 created the `code-intelligence://blame/{repo}/{file_path}` resource routing stub. Phase 8 graduates this to a first-class MCP resource handler and MCP tool with subscription support.

### 10.2 Blame Resource Handler

`mcp_server/resources/blame.py` handles `code-intelligence://blame/{repo}/{file_path}`.

Resource payload:

```text
BlameResource
  repo_id : str
  file_path : str      # Repo-relative
  snapshot_id : str
  git_sha : str
  entries : list[BlameEntry] | ArtifactRef  # Inline for small files; artefact ref for large
  commit_chain : list[CommitRecord]
  is_dirty : bool
  dirty_lines : list[int] | None
  diagnostics : list[str]
  provenance : ProvenanceRecord

BlameEntry
  start_line : int
  end_line : int
  commit_sha : str
  author_name : str
  author_email : str
  author_ts : str
  committer_ts : str
  summary : str
  body : str | None
  original_file : str | None    # If file was renamed
  original_line : int | None

CommitRecord
  sha : str
  author_name : str
  author_ts : str
  summary : str
  parents : list[str]
```

Subscription:

- Subscribable. `notifications/resources/updated` fires after `graph_update` refreshes blame records for the file.

Resource rules:

- Untracked files return an explicit `untracked` status in diagnostics.
- Binary files return a `binary_file` diagnostic.
- Dirty lines are tracked when the current snapshot is a dirty worktree snapshot.

### 10.3 `git_blame_chain` MCP Tool

The tool extends the resource with interactive options.

Tool input:

```text
git_blame_chain input
  repo : str
  file : str
  line : int | None             # Return blame for a specific line only
  line_range : tuple[int, int] | None   # Start/end line range
  follow_renames : bool | None  # Follow file renames through history; default True
  depth : int | None            # Number of parent commits to include; default 3
  snapshot : str | None
```

Tool output:

```text
git_blame_chain output
  repo_id : str
  file_path : str
  snapshot_id : str
  entries : list[BlameEntry]
  commit_chain : list[CommitRecord]
  file_history : list[FileHistoryEntry]
  rename_chain : list[str] | None    # File paths this file was known as historically
  diagnostics : list[str]
  run_event_ids : list[str]

FileHistoryEntry
  commit_sha : str
  file_path : str
  change_type : str    # added, modified, deleted, renamed
  author_name : str
  author_ts : str
  summary : str
```

### 10.4 Blame Tool Behavior

1. Validate repo and file path.
2. Read Phase 3 blame-chain artefact from the graph store.
3. If `follow_renames=True`, trace the rename chain through git log.
4. Filter to requested line or line range if specified.
5. Build `CommitRecord` chain up to `depth` parents.
6. Return typed payload.

Rules:

- Tool does not run `git blame` live unless no cached record exists and a safe refresh is possible.
- Safe refresh is only allowed in read mode.
- Dirty lines are included when the snapshot is a worktree snapshot.

### 10.5 Blame Tool Permission Descriptor

```text
required_mode : read/search
path_scope : registered repo root
network_requirement : none
side_effect_class : read_only (telemetry only)
approval_requirement : not required
```

### 10.6 Blame Tests

Required tests:

- Blame resource returns entries for committed fixture file.
- Blame entry includes author, timestamp, and commit summary.
- Line-specific query filters entries.
- Line range query filters correctly.
- Rename chain tracked through file history.
- Untracked file: diagnostic, no entries.
- Binary file: diagnostic, no entries.
- Dirty line tracking for worktree snapshot.
- Subscription: notification fires after `graph_update` refreshes blame.

---

## 11. LLM Answer Synthesis Interface

### 11.1 Purpose

`synthesis.py` defines the typed boundary for LLM involvement in repo-QA answers. The LLM cannot see or self-assign confidence levels. Confidence is computed by the evidence assembler before and after synthesis.

### 11.2 Synthesis Contract

```text
SynthesisInput
  question_class : QuestionClass
  normalized_question : str
  evidence_summary : EvidenceSummary    # Pre-assembled, typed
  graph_nodes : list[GraphNodeRef]
  graph_paths : list[GraphPath]
  interface_contracts : list[InterfaceContractResult]
  blame_entries : list[BlameEntry] | None
  max_tokens : int
  mode : SynthesisMode   # narrative, structured, technical_summary

SynthesisOutput
  answer_text : str
  cited_node_ids : list[str]     # From graph_nodes; LLM must cite only provided nodes
  confidence_claim : str | None  # LLM may suggest a confidence LEVEL; assembler overrides it
  synthesis_model : str
  synthesis_tokens_used : int
  derivation : str = "llm"

EvidenceSummary
  source_count : int
  highest_evidence_confidence : ConfidenceLevel
  has_graph_path : bool
  has_interface_contract : bool
  has_blame_chain : bool
  question_class_threshold_met : bool   # Whether the ship gate for this class is met
```

Rules:

- LLM receives only the `EvidenceSummary`, not raw source files.
- LLM receives only `GraphNodeRef` objects, not the full graph store.
- The assembler always overrides `confidence_claim` from the LLM with the evidence-derived confidence.
- LLM synthesis is optional. When synthesis is disabled, the answer is assembled directly from evidence.
- LLM synthesis tokens count against the caller's context budget.

### 11.3 Synthesis Modes

- `narrative`: prose explanation suitable for a developer reading a chat interface.
- `structured`: machine-readable answer with evidence citations in a consistent schema.
- `technical_summary`: one or two technical sentences, no narrative filler.

### 11.4 Synthesis Tests

Required tests:

- `SynthesisInput` validates.
- Confidence override: LLM claim of `parser` is rejected when evidence is `heuristic`.
- Synthesis disabled: answer assembled from evidence alone.
- LLM receives no raw source file content.
- `cited_node_ids` in output are a subset of nodes in input.

---

## 12. Evidence Assembler And Confidence Rules

### 12.1 Purpose

`evidence_assembler.py` collects all evidence for a question and produces the final `AnswerEvidence` list. `confidence.py` applies per-question-class confidence rules.

### 12.2 Evidence Types

```text
AnswerEvidence
  evidence_id : str
  evidence_type : EvidenceType
  node_id : str | None
  node_type : str | None
  file_path : str | None
  span : Span | None
  content_snippet : str | None     # Bounded; never the full file
  confidence : ConfidenceLevel
  source : str                     # Lookup strategy, plugin, backend, etc.

EvidenceType
  FILE_NODE              # A matched file node in the graph
  SYMBOL_NODE            # A matched symbol node
  GRAPH_PATH             # A multi-hop path
  INTERFACE_CONTRACT     # An InterfaceRecord match
  BLAME_ENTRY            # A blame chain entry
  DOCUMENT_LINK          # A doc/spec node linked to code
  SAST_ALERT             # A warned_by alert node
```

### 12.3 Per-Question-Class Confidence Rules

**`FILE_LOC`:**
- One or more `FILE_NODE` or `SYMBOL_NODE` with `confidence=parser` → answer confidence `parser`.
- Only `SYMBOL_NODE` with `confidence=analyser` → `analyser`.
- Only keyword matches → `heuristic`.
- No matches → `unknown`.

**`SYMBOL_LOC`:**
- Exact symbol match via graph → `parser`.
- Fuzzy symbol match → `analyser`.
- Interface-link expanded result → same as underlying symbol match.
- No matches → `unknown`.

**`BEHAVIOUR_TRACE`:**
- Always capped at `heuristic` until ship-gate met.
- Graph path found → `heuristic`.
- No path → `unknown`.
- LLM synthesis present but no graph path → `heuristic` with explicit uncertainty note.

**`CONTRACT_CHECK`:**
- `DOCUMENT_LINK` + `SAST_ALERT` confirming the check → `analyser`.
- `DOCUMENT_LINK` without predicate evidence → `heuristic`.
- No doc/spec node found → `unknown`.

**`OTHER`:**
- Always `heuristic`. No ship-gate applies.

### 12.4 Uncertainty Rules

An answer carries an `uncertainty` field when:

- The behaviour-trace ship-gate is not met.
- Graph snapshot is stale.
- Evidence is from a mixed snapshot.
- The question class is `OTHER`.
- Confidence is `heuristic` for any safety-sensitive question.

### 12.5 Evidence Assembler Tests

Required tests:

- FILE_LOC with parser evidence → confidence `parser`.
- BEHAVIOUR_TRACE with graph path → confidence capped at `heuristic`.
- CONTRACT_CHECK with document link only → `heuristic`.
- No evidence → `unknown` with reason.
- Mixed snapshot evidence → uncertainty note.
- `content_snippet` is bounded (never full file content).

---

## 13. Answer Model

### 13.1 `RepoAnswer`

```text
RepoAnswer
  answer_id : str
  question_id : str
  question_class : QuestionClass
  answer_text : str             # Human-readable answer
  confidence : ConfidenceLevel
  confidence_reason : str
  evidence : list[AnswerEvidence]
  graph_node_ids : list[str]
  graph_paths : list[GraphPath]
  interface_contracts : list[InterfaceContractResult]
  blame_entries : list[BlameEntry] | None
  uncertainty : str | None
  recommended_action : str | None
  synthesis_mode : str | None
  synthesis_model : str | None
  synthesis_tokens : int | None
  run_event_ids : list[str]
  snapshot_ids : dict[str, str]
  schema_version : str
```

### 13.2 Answer Completeness Rules

An answer is considered well-formed when:

- `evidence` is non-empty for any confidence above `unknown`.
- `graph_node_ids` contains at least one node ID when confidence is `parser` or `analyser`.
- `uncertainty` is populated when `confidence=heuristic` and the question is `BEHAVIOUR_TRACE`.
- `recommended_action` is populated when `confidence=unknown`.

### 13.3 Recommended Actions

When confidence is `unknown`, `recommended_action` should suggest one of:

- "Run `graph_build` to index this repository."
- "Check if the behaviour-trace ship-gate threshold has been met."
- "Register the repository containing the referenced symbol."
- "Run `plugin_reload` to refresh interface index after IDL changes."
- "Provide more specific code token in the question."

### 13.4 Answer Tests

Required tests:

- `RepoAnswer` validates against schema.
- Well-formed check enforced: non-empty evidence for non-unknown answers.
- Recommended action present for `unknown`.
- `uncertainty` present for `heuristic` behaviour-trace.
- `graph_node_ids` populated for `parser` confidence answers.

---

## 14. `classify_repo_question` MCP Tool

### 14.1 Purpose

A standalone tool that classifies a question without answering it. Useful for routing, debugging, and evaluation.

### 14.2 Tool Input

```text
classify_repo_question input
  question : str
  repos : list[str] | None
  use_llm_fallback : bool | None    # Default from server config; False in budget mode
```

### 14.3 Tool Output

```text
classify_repo_question output
  question_id : str
  question_class : str
  confidence : str
  derivation : str          # deterministic, llm_fallback
  matched_rules : list[str]
  score : float
  alternative_class : str | None
  alternative_score : float | None
  run_event_ids : list[str]
```

### 14.4 Permission Descriptor

```text
required_mode : read/search
path_scope : none (classification is stateless)
network_requirement : conditional (llm_fallback may require model endpoint)
side_effect_class : read_only
approval_requirement : not required
```

### 14.5 `classify_repo_question` Tests

Required tests:

- FILE_LOC question classified correctly.
- SYMBOL_LOC question classified correctly.
- BEHAVIOUR_TRACE question classified correctly.
- CONTRACT_CHECK question classified correctly.
- OTHER question classified.
- LLM fallback disabled when `use_llm_fallback=False`.
- Classification result carries `matched_rules`.

---

## 15. `answer_repo_question` MCP Tool

### 15.1 Purpose

The primary repo-QA tool. Routes questions through the appropriate answer path based on classification, assembles evidence, optionally invokes synthesis, and returns a `RepoAnswer`.

### 15.2 Tool Input

```text
answer_repo_question input
  question : str
  repos : list[str] | None
  question_class_hint : str | None     # Override classification if known
  synthesis : bool | None              # Whether to invoke LLM synthesis; default True
  synthesis_mode : str | None          # narrative, structured, technical_summary
  max_evidence : int | None            # Cap on evidence items; default 20
  max_hops : int | None                # For behaviour-trace traversal; default 8
  snapshot : str | None
  include_blame : bool | None          # Include blame evidence; default False
  budget : dict | None                 # Token and time budget overrides
```

### 15.3 Tool Output

The tool returns a `RepoAnswer` serialized as the tool payload.

### 15.4 Tool Behavior

1. Normalize and classify the question (calling classifier internally).
2. Route to the appropriate answer path:
   - `FILE_LOC` → deterministic file lookup → graph confirmation → evidence assembly.
   - `SYMBOL_LOC` → deterministic symbol lookup → interface link expansion → graph path builder → evidence assembly.
   - `BEHAVIOUR_TRACE` → intent extraction → traversal plan → graph/cross-language traversal → evidence assembly.
   - `CONTRACT_CHECK` → document link lookup → SAST/predicate evidence → evidence assembly.
   - `OTHER` → keyword lookup (best effort) → evidence assembly with `heuristic` cap.
3. If `synthesis=True` and evidence exists, invoke synthesis interface.
4. Apply confidence rules.
5. Apply ship-gate check.
6. Return `RepoAnswer`.

### 15.5 Budget Enforcement

Rules:

- LLM synthesis is disabled when context budget is below the configured minimum.
- Traversal depth is capped by context budget.
- Evidence items are capped by `max_evidence`.
- Token spend on synthesis is logged as a run event.

### 15.6 Ship-Gate Check

`ship_gate.py` implements the configurable threshold checks:

```text
ShipGateConfig
  file_loc_em_threshold : float       # Default 0.80 (80% EM on file-loc subset)
  behaviour_trace_threshold : float   # Default 0.70 (70% on swe-qa / coreqa)
  file_loc_gate_met : bool            # Updated by eval harness
  behaviour_trace_gate_met : bool     # Updated by eval harness
```

Rules:

- `FILE_LOC` answers may reach `parser` confidence regardless of gate status (deterministic lookup).
- `BEHAVIOUR_TRACE` answers are capped at `heuristic` when `behaviour_trace_gate_met=False`.
- Ship-gate status is recorded in every `RepoAnswer.run_event_ids` reference.
- Gate thresholds are read from workspace config, not hard-coded.

### 15.7 `answer_repo_question` Tests

Required tests:

- FILE_LOC question returns file node evidence.
- SYMBOL_LOC question returns symbol node evidence.
- BEHAVIOUR_TRACE question returns graph paths or `unknown`.
- CONTRACT_CHECK question returns document link.
- Evidence assembled before synthesis.
- Synthesis disabled: answer assembled from evidence only.
- `unknown` returned when no evidence found.
- Ship-gate enforced for behaviour-trace.
- Budget cap terminates traversal.

---

## 16. `get_interface_contract` MCP Tool

### 16.1 Purpose

`get_interface_contract` provides a tool-call interface for interface contract retrieval, as a typed wrapper over the Phase 7 interface resources. It is marked `[PY-CODE]` in the architecture — no LLM is involved.

### 16.2 Tool Input

```text
get_interface_contract input
  plugin_id : str
  interface_name : str
  repo : str | None
  include_operations : bool | None     # Default True
  include_node_refs : bool | None      # Default True
```

### 16.3 Tool Output

```text
get_interface_contract output
  interface_record : InterfaceRecord    # From Phase 7
  matched_operations : list[InterfaceOperation]
  server_node_refs : list[GraphNodeRef]
  client_node_refs : list[GraphNodeRef]
  generated_artifact_refs : list[ArtifactRef]
  confidence : str
  snapshot_ids : dict[str, str]
  run_event_ids : list[str]
```

### 16.4 Tool Behavior

1. Look up `InterfaceRecord` from Phase 7 plugin registry.
2. Filter operations if requested.
3. Resolve server and client node IDs to `GraphNodeRef` objects.
4. Return typed payload.

Rules:

- Returns `ResourceNotFound` for unknown plugin_id or interface_name.
- Returns stale-snapshot diagnostic if interface was indexed against a different snapshot.

### 16.5 Permission Descriptor

```text
required_mode : read/search
path_scope : registered repos
network_requirement : none
side_effect_class : read_only
approval_requirement : not required
```

### 16.6 `get_interface_contract` Tests

Required tests:

- Known interface returns `InterfaceRecord` with operations.
- Unknown plugin_id: typed not-found.
- Unknown interface_name: typed not-found.
- `include_operations=False` omits operation list.
- Node refs resolved to `GraphNodeRef`.

---

## 17. Answer Quality Gates And Ship Thresholds

### 17.1 Purpose

`ship_gate.py` enforces evidence-quality constraints on answers before they are returned to callers. It also provides the measurement infrastructure that Phase 10 will use to update gate status after eval runs.

### 17.2 Gate Architecture

```text
AnswerQualityGate
  check(answer: RepoAnswer, gate_config: ShipGateConfig) -> GateResult

GateResult
  passed : bool
  gate_name : str
  reason : str | None
  confidence_cap : ConfidenceLevel | None  # Applied if not passed
```

Gates applied in order:

1. **Evidence presence gate**: reject confidence above `unknown` for answers with empty `evidence`.
2. **Behaviour-trace gate**: cap at `heuristic` when `gate_config.behaviour_trace_gate_met=False`.
3. **Stale-snapshot gate**: downgrade confidence by one level when evidence is from a stale or mixed snapshot.
4. **Content-snippet gate**: reject `parser` confidence when only content snippets (not graph nodes) are cited.

### 17.3 Gate Configuration

Gate thresholds are stored in the workspace configuration, not hard-coded.

Configuration fields:

```text
qa_gate_config:
  file_loc_em_threshold: 0.80
  behaviour_trace_threshold: 0.70
  file_loc_gate_met: false      # Updated by eval harness
  behaviour_trace_gate_met: false
  stale_snapshot_tolerance_seconds: 3600
```

### 17.4 Gate State Update

Phase 10 (evaluation harness) will update `file_loc_gate_met` and `behaviour_trace_gate_met` after eval runs. Phase 8 reads these values but does not set them. The gate state is read from the workspace operational store, not from a mutable config file.

### 17.5 Gate Tests

Required tests:

- Empty evidence → confidence forced to `unknown`.
- Behaviour-trace gate not met → confidence capped at `heuristic`.
- Stale snapshot evidence → confidence downgraded.
- All gates pass for graph-confirmed file-loc answer.
- Gate state update path tested (mock eval update).

---

## 18. Evidence-Cited Answer Format

### 18.1 Evidence Citation Requirements

Every answer produced by `answer_repo_question` must include evidence citations that allow a downstream tool or human reviewer to independently verify the answer.

Required citation fields per evidence item:

- `node_id`: the Phase 2 graph node ID.
- `file_path`: repo-relative path.
- `span`: line numbers if the evidence is span-level.
- `source`: which lookup strategy or backend produced this evidence.
- `confidence`: the confidence of this specific evidence item.

### 18.2 Content Snippet Rules

Rules:

- Content snippets must be bounded: maximum 5 lines of source code per evidence item.
- Full file content must never appear in an answer payload.
- Snippets are stored as `ArtifactRef` pointers, not inline strings, when they exceed the bounded limit.
- Snippet retrieval is opt-in via `include_snippets=True` on the tool call.

### 18.3 Provenance Chain

Every `RepoAnswer` carries:

- `snapshot_ids`: the snapshot of each repo at answer time.
- `run_event_ids`: references to operational run events.
- `synthesis_model`: the model used for synthesis if applicable.
- `schema_version`: for reproducibility.

### 18.4 Tests

Required tests:

- Evidence item contains `node_id`, `file_path`, `source`, and `confidence`.
- Snippet is bounded to five lines.
- Full file content rejected from answer payload.
- `snapshot_ids` populated for all involved repos.

---

## 19. Security, Privacy, And Scope Constraints

### 19.1 Question Input Safety

Rules:

- Question text is treated as untrusted input.
- Code token extraction from questions must not execute extracted tokens.
- LLM fallback classifier receives only normalized question text, not raw user context.
- Question text is redacted from operational logs when it contains code values matching secret patterns.

### 19.2 Answer Content Safety

Rules:

- Content snippets are bounded; full source files are never included.
- Blame entry email addresses are redacted from answers unless the workspace privacy policy explicitly allows them.
- Interface contract schemas stored in answers must not contain sensitive field values from request/response bodies.

### 19.3 Scope Restriction

Rules:

- Answers are scoped to registered repos only.
- Questions that resolve to nodes in unregistered repos return `unknown` with a diagnostic.
- Cross-repo answers carry the authorization context of both repos.

### 19.4 LLM Synthesis Input Restrictions

Rules:

- LLM synthesis input contains no secrets.
- Synthesis input is constructed from pre-assembled, typed evidence — not raw user context.
- HC6 (no red-class data in prompts) must be enforced by checking evidence items before synthesis.

---

## 20. Test Plan

### 20.1 Question And Classifier Tests

Required:

- Question normalization removes filler, preserves code tokens.
- All five question classes correctly classified by deterministic rules.
- Ambiguous question produces alternative class.
- LLM fallback disabled in budget mode.

### 20.2 Lookup Tests

Required:

- File lookup: exact path, module name, symbol-to-file, keyword.
- Symbol lookup: exact name, qualified name, fuzzy.
- Interface link expansion.
- Empty result with `unknown` confidence.

### 20.3 Graph-Path Tests

Required:

- Path built correctly for fixture graph.
- Document link found for `documents` edge.
- Confidence is minimum across path edges.
- No path between disconnected nodes.

### 20.4 Behaviour-Trace Tests

Required:

- Intent extraction from natural language.
- Graph traversal plan built.
- `unknown` returned when no start node.
- Confidence capped at `heuristic`.
- Cross-language traversal invoked for cross-language intent.

### 20.5 Interface Lookup Tests

Required:

- Name match returns record.
- Symbol-linked interface found via edge.
- File-path lookup works for IDL file.

### 20.6 Blame Tests

Required:

- Blame resource returns entries.
- Tool with line filter returns filtered entries.
- Rename chain tracked.
- Subscription fires after `graph_update`.

### 20.7 Evidence Assembler And Confidence Tests

Required:

- FILE_LOC with graph-confirmed match → `parser`.
- BEHAVIOUR_TRACE → always `heuristic`.
- CONTRACT_CHECK with doc link + SAST alert → `analyser`.
- Mixed snapshot → uncertainty note.

### 20.8 Answer Model Tests

Required:

- Well-formed check.
- Recommended action for `unknown`.
- `uncertainty` for behaviour-trace.

### 20.9 MCP Tool Tests

Required:

- `classify_repo_question`: all five classes.
- `answer_repo_question`: FILE_LOC, SYMBOL_LOC, BEHAVIOUR_TRACE, CONTRACT_CHECK.
- `answer_repo_question`: unknown when no evidence.
- `get_interface_contract`: known and unknown interface.
- `git_blame_chain`: fixture file with line filter.

### 20.10 Ship-Gate Tests

Required:

- Behaviour-trace capped when gate not met.
- Gate config read from workspace store.
- Evidence-presence gate enforced.

### 20.11 Regression Tests

Required:

- `classify_repo_question` tool descriptor snapshot.
- `answer_repo_question` tool descriptor snapshot.
- `get_interface_contract` tool descriptor snapshot.
- `git_blame_chain` tool descriptor snapshot.
- Blame resource descriptor snapshot.

---

## 21. Work Packages

### P8.1 Question Model, Normalizer, And Classifier

Build:

- `QuestionClass` enum.
- `RepoQuestion` model.
- Normalizer.
- Deterministic rule classifier.
- LLM fallback interface stub.

Deliverables:

- `qa/question.py`, `qa/classifier.py`
- Question and classifier tests.
- Question fixture files.

Acceptance:

- All five question classes correctly classified by deterministic rules on fixture cases.

### P8.2 Deterministic File And Symbol Lookup

Build:

- `FileLocLookup` with five strategies.
- `SymbolLocLookup` with four strategies.
- `LookupResult` model.

Deliverables:

- `qa/lookup.py`
- Lookup tests.

Acceptance:

- Exact file and symbol matches return `parser` confidence for fixture graph.

### P8.3 Graph-Path Answer Builder

Build:

- `GraphPathBuilder`.
- `GraphPath` and `DocumentLink` models.

Deliverables:

- `qa/graph_query.py`
- Graph-path tests.

Acceptance:

- Caller-to-callee path found for fixture graph.

### P8.4 Behaviour-Trace Traversal

Build:

- Intent extraction.
- Traversal plan builder.
- Phase 7 traversal engine integration.
- `unknown` return path.

Deliverables:

- `qa/behaviour_trace.py`
- Behaviour-trace tests.

Acceptance:

- Cross-language traversal triggered for cross-language intent; `unknown` returned when no start node.

### P8.5 Interface Contract Lookup

Build:

- `InterfaceContractResult` model.
- Three lookup paths: name, symbol, file.

Deliverables:

- `qa/interface_lookup.py`
- Interface lookup tests.

Acceptance:

- Name-based and symbol-linked lookups work for Phase 7 fixture.

### P8.6 Git Blame Chain Resource And Tool

Build:

- `BlameResource` handler.
- `BlameEntry` and `CommitRecord` models.
- `git_blame_chain` MCP tool.
- Subscription integration.

Deliverables:

- `mcp_server/resources/blame.py`
- `mcp_server/tools/blame.py`
- `qa/blame.py`
- Blame resource and tool tests.

Acceptance:

- Blame resource returns entries for fixture file. Tool filters by line. Subscription fires after `graph_update`.

### P8.7 LLM Synthesis Interface

Build:

- `SynthesisInput`, `SynthesisOutput`, `EvidenceSummary` models.
- `SynthesisInterface` abstract class.
- Null synthesis adapter (returns evidence-only answer text).

Deliverables:

- `qa/synthesis.py`
- Synthesis tests.

Acceptance:

- Null adapter returns evidence-only answer. Confidence override enforced.

### P8.8 Evidence Assembler, Confidence Rules, And Answer Model

Build:

- `AnswerEvidence` and `EvidenceType`.
- Per-question-class confidence rules.
- `EvidenceAssembler`.
- `RepoAnswer` model.
- Well-formed check.

Deliverables:

- `qa/evidence_assembler.py`, `qa/confidence.py`, `qa/answer.py`
- Assembler, confidence, and answer tests.

Acceptance:

- FILE_LOC graph-confirmed → `parser`. BEHAVIOUR_TRACE → `heuristic`.

### P8.9 Ship-Gate And Quality Gates

Build:

- `ShipGateConfig`.
- `AnswerQualityGate` with four gates.
- Gate state read from workspace operational store.

Deliverables:

- `qa/ship_gate.py`
- Ship-gate tests.

Acceptance:

- Behaviour-trace capped when gate not met. Evidence-presence gate enforced.

### P8.10 MCP Tools And Regression Tests

Build:

- `classify_repo_question` tool.
- `answer_repo_question` tool (orchestrates all QA modules).
- `get_interface_contract` tool.
- Tool descriptor regression tests.
- QA integration test.

Deliverables:

- `mcp_server/tools/qa.py`
- Tool and regression tests.

Acceptance:

- All four MCP tools pass their integration tests.

---

## 22. Suggested Implementation Order

Recommended order:

1. Question model and normalizer.
2. Deterministic classifier.
3. Deterministic file and symbol lookup.
4. `classify_repo_question` tool (validates classifier).
5. Graph-path answer builder.
6. Evidence assembler and confidence rules.
7. Answer model and well-formed check.
8. Ship-gate module.
9. `answer_repo_question` tool (FILE_LOC path first).
10. Behaviour-trace traversal.
11. `answer_repo_question` tool (BEHAVIOUR_TRACE path).
12. Interface-contract lookup.
13. `get_interface_contract` tool.
14. Git blame chain resource handler (Phase 3/4 graduation).
15. `git_blame_chain` tool.
16. Blame subscription integration.
17. LLM synthesis interface and null adapter.
18. Synthesis integration into `answer_repo_question`.
19. `CONTRACT_CHECK` and `OTHER` paths.
20. Regression test harness.

Reasoning:

- Classifier and deterministic lookup first because they are testable independently.
- FILE_LOC path before BEHAVIOUR_TRACE because it is deterministic and does not depend on ship-gate calibration.
- Graph-path builder before behaviour-trace because behaviour-trace builds on it.
- Blame tool after the resource handler because the tool adds interactive capabilities over the resource.
- LLM synthesis last because it is optional and the null adapter allows full integration testing without a model endpoint.

---

## 23. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 8 |
|---|---|
| Phase 9 - Fault localisation | `classify_repo_question` pattern for question-type routing; `FileLocLookup` as a baseline lookup path before embedding retrieval; blame chain evidence as an FL prior |
| Phase 10 - Evaluation harness | `answer_repo_question` as the evaluation target for `swd-bench` Functionality-Localization and `swe-qa`/`coreqa` behaviour subsets; `ShipGateConfig` updated by eval harness after T2 runs |
| Phase 11 - Patch review | `get_interface_contract` for API/ABI compatibility checks; blame chain for change-attribution context |
| Phase 12 - SAST repair | `CONTRACT_CHECK` QA path to find spec clauses relevant to an alert |
| Phase 13 - Bug-resolve | `answer_repo_question` for initial investigation; `get_interface_contract` for interface context; blame chain for change attribution; behaviour-trace for end-to-end flow context |
| Phase 14 - Implementation-check | `BEHAVIOUR_TRACE` and `CONTRACT_CHECK` paths for clause-to-code grounding (stage 4 soft probe); `ShipGateConfig.behaviour_trace_gate_met` as gating condition for soft verdict trust |
| Phase 15 - Blast radius | `get_interface_contract` for interface impact documentation |
| Phase 17 - Memory | `graph_node_ids` and `snapshot_ids` in `RepoAnswer` as stable trajectory anchors |
| Phase 18 - Release gates | `swd-bench` Functionality-Localization and `swe-qa`/`coreqa` eval results as T2 repo-QA metrics; `file_loc_gate_met` and `behaviour_trace_gate_met` as release-gate inputs |

---

## 24. Exit Criteria Mapping

Source Phase 8 exit criterion:

- File-location questions return cited files/symbols.

Concrete acceptance:

- `answer_repo_question` with a FILE_LOC question against the fixture repo returns at least one `FILE_NODE` or `SYMBOL_NODE` evidence item with `file_path` set.
- Evidence item carries `node_id`, `source`, and `confidence`.
- Returned `confidence` is `parser` for exact graph matches.

Source Phase 8 exit criterion:

- Behaviour-trace questions return graph paths or `unknown`.

Concrete acceptance:

- `answer_repo_question` with a BEHAVIOUR_TRACE question for a fixture that has a cross-language route returns at least one `GRAPH_PATH` evidence item.
- `answer_repo_question` with a BEHAVIOUR_TRACE question for an unindexed flow returns a `RepoAnswer` with `confidence=unknown` and `recommended_action` populated.
- Returned confidence is never above `heuristic` for BEHAVIOUR_TRACE.

Source Phase 8 exit criterion:

- Answers that lack graph/code evidence cannot be marked high confidence.

Concrete acceptance:

- Answer with empty `evidence` list: `confidence=unknown` enforced by gate.
- Answer built entirely from LLM text without graph node citations: confidence not promoted above `heuristic`.
- `AnswerQualityGate` test demonstrates enforcement.

---

## 25. Definition Of Done

Phase 8 is done when:

- Question model, normalizer, and `QuestionClass` enum are implemented and tested.
- Deterministic classifier correctly classifies all five question classes for fixture cases.
- File lookup and symbol lookup return graph-confirmed evidence for fixture queries.
- Graph-path answer builder builds paths for multi-hop fixture queries.
- Behaviour-trace traversal invokes `CrossLanguageTraverser` for cross-language questions.
- Behaviour-trace answers are capped at `heuristic` when ship-gate is not met.
- Interface-contract lookup returns `InterfaceRecord` for Phase 7 fixture interfaces.
- Git blame chain resource handler serves entries for committed fixture files.
- `git_blame_chain` tool filters by line and tracks rename chains.
- LLM synthesis null adapter produces evidence-only answers.
- Evidence assembler applies per-question-class confidence rules.
- Ship-gate enforces confidence caps from workspace configuration.
- `classify_repo_question`, `answer_repo_question`, `get_interface_contract`, and `git_blame_chain` MCP tools are implemented and tested.
- `code-intelligence://blame/{repo}/{file_path}` resource handler is subscribable.
- All Phase 3/4/5/6/7 tests continue to pass.

---

## 26. Risks, Mitigations, Completion Report, And Minimal First Slice

### 26.1 Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Deterministic classifier misroutes questions | Wrong answer path, misleading confidence | Separate test set for each question class; log matched rules in classification result; operator can override with `question_class_hint` |
| Behaviour-trace returns confident-sounding prose without graph evidence | Misleads downstream consumers | Ship-gate cap enforced unconditionally; `uncertainty` message required in all BEHAVIOUR_TRACE answers; LLM cannot self-certify |
| Phase 7 plugin not indexed when `answer_repo_question` calls `get_interface_contract` | Missing interface evidence | Return capability diagnostic when plugin unavailable; degrade to symbol-level evidence |
| File lookup returns wrong file for common symbol names in large repos | Incorrect evidence citation | Scope file lookup to repos provided in question; rank by graph edge density (symbols with more calls more likely to be the right one) |
| Blame records stale after large refactor | Blame evidence misleading | Record blame freshness in `BlameEntry.snapshot_id`; stale blame triggers uncertainty note |
| LLM synthesis leaks secret content if evidence assembler passes raw code | HC6 violation | Evidence assembler enforces snippet bounds and secret-scan before synthesis input construction |
| `answer_repo_question` too slow for interactive use | Developer experience degraded | Cap traversal depth and evidence count; default synthesis mode to `technical_summary`; task-capable for deep traversal |
| CONTRACT_CHECK answers confuse spec clauses with code comments | Wrong doc-link evidence | `documents` edge only populated by Phase 3/5 document parsers, not raw comment text; contract-check confidence requires a `design_clause` node, not a `file` node |
| Ship-gate thresholds never updated because eval harness not yet built | BEHAVIOUR_TRACE always capped | Gate status in workspace config can be manually overridden by operator for development testing; default remains `false` until Phase 10 eval harness sets it |

### 26.2 Completion Report Template

When Phase 8 implementation is complete, report:

```text
Phase 8 completion report

Implemented:
- Question model, normalizer, and QuestionClass enum:
- Deterministic classifier (5 classes):
- LLM fallback classifier stub:
- File and symbol lookup:
- Graph-path answer builder:
- Behaviour-trace traversal:
- Interface-contract lookup:
- Git blame chain resource:
- git_blame_chain MCP tool:
- LLM synthesis null adapter:
- Evidence assembler and confidence rules:
- Answer model and well-formed check:
- Ship-gate module:
- classify_repo_question MCP tool:
- answer_repo_question MCP tool:
- get_interface_contract MCP tool:

Verification:
- Classifier tests (all 5 classes):
- File and symbol lookup tests:
- Behaviour-trace tests:
- Interface lookup tests:
- Blame resource and tool tests:
- Evidence assembler tests:
- Ship-gate tests:
- MCP tool tests:
- Regression harness:
- Local verify command:

Exit criteria:
- File-location questions return cited files/symbols:
- Behaviour-trace questions return graph paths or unknown:
- Answers without graph evidence capped at heuristic/unknown:
- Phase 3/4/5/6/7 tests still pass:

Known limitations:
-

Follow-up for Phase 9 (Fault Localisation):
-
```

### 26.3 Minimal First Slice Within Phase 8

If Phase 8 needs to be split further, implement this first:

1. Question model, normalizer, and `QuestionClass` enum.
2. Deterministic classifier for `FILE_LOC` and `SYMBOL_LOC` only.
3. Deterministic file and symbol lookup.
4. Evidence assembler with FILE_LOC confidence rules.
5. `RepoAnswer` model.
6. `classify_repo_question` tool.
7. `answer_repo_question` tool (FILE_LOC and SYMBOL_LOC paths only).
8. Git blame chain resource handler (graduating Phase 3/4).
9. `git_blame_chain` tool.
10. FILE_LOC and SYMBOL_LOC integration tests on fixture.

This minimal slice delivers the two highest-accuracy, fully-deterministic QA paths and the blame tool without requiring LLM synthesis, behaviour-trace infrastructure, or interface-contract lookup. BEHAVIOUR_TRACE and CONTRACT_CHECK paths follow in subsequent slices.
