# LLM-SCA Tooling Phase 2 Implementation Plan: Local Graph Store and Repository Registry

> Date: 2026-05-09
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 2 - Local Graph Store and Repository Registry
> Primary objective: implement the local persistence layer that stores registered repositories, graph facts, snapshots, harness metadata, operational run evidence, incidents, readiness reports, and promotion records.

---

## 1. Phase Summary

Phase 2 turns the Phase 1 schemas into durable local state. It provides the repository registry, workspace metadata, local graph store, snapshot ledger, harness metadata store, operational evidence store, and basic export/import mechanics that later indexing, MCP, workflow, evaluation, and memory phases depend on.

This phase is still not an indexing or workflow phase. It should not scan source trees, run parsers, invoke LLMs, execute static analysis, or expose MCP routes. It should store and query typed facts that other components produce.

The central rule for this phase is:

```text
Every persisted graph, snapshot, run, policy, budget, incident, readiness, and promotion fact
must remain tied to schema version, repository identity, provenance, and the harness condition
under which it was produced.
```

Phase 2 should optimize for:

- Correctness.
- Auditability.
- Snapshot awareness.
- Queryability for small and medium local workspaces.
- Clear migration and export/import behavior.
- Deterministic tests over large-scale performance.

### Architecture Coverage

Phase 2 covers:

- F1 - Graph persistence.
- F11 - Operational evidence persistence.
- Multi-repository workspace.
- Snapshot-aware evidence retention.
- Storage support for later MCP resources:
  - `code-intelligence://repos`
  - `code-intelligence://graph/{repo}`
  - `code-intelligence://graph/slice/{repo}/{files}`
  - `code-intelligence://runs/{run_id}`
  - `code-intelligence://runs/{run_id}/harness-condition`
  - `code-intelligence://operations/{repo}/ledger`
  - `code-intelligence://governance/{repo}/policy`
  - `code-intelligence://governance/{repo}/manifest-state`
  - `code-intelligence://readiness/{repo}`
  - `code-intelligence://incidents/{incident_id}`

### Inherited Paper Anchors

Use these anchors in Phase 2 issues, ADRs, migration notes, and storage design records:

- `rig`
- `logiclens`
- `graph-memory-rl`
- `hafixagent`
- `agenttrace`
- `aer`
- `schema-grounded-memory`

Operational and harness-related storage notes may also reference:

- `opendev`
- `runtime-governance`
- `workstream`
- `needle-repo`
- `agentic-harness-engineering`

## Technology Stack

Libraries directly used in Phase 2 implementation:

| Library | PyPI package | Version constraint | Purpose in this phase |
|---|---|---|---|
| SQLModel | `sqlmodel` | `>=0.0.21` | ORM layer (Pydantic v2 + SQLAlchemy 2.0 async); table models for all Phase 2 tables |
| Alembic | `alembic` | `>=1.13` | Database migration management; `0001_initial.py` is the first migration script in this phase |
| aiosqlite | `aiosqlite` | `>=0.20` | Async SQLite driver; connection URL: `sqlite+aiosqlite:///.llm-sca/workspace.db` |
| asyncpg | `asyncpg` | `>=0.29` | Async PostgreSQL driver for production use; connection URL: `postgresql+asyncpg://...` |
| NetworkX | `networkx` | `>=3.3` | In-memory graph traversal; ego graph, path, and neighbour queries load a `nx.DiGraph` subgraph from SQLModel rows |
| orjson | `orjson` | `>=3.10` | JSON column serialization (`payload_json`, `capabilities_json`, `metadata_json`) and graph export/import bundles |

### Critical conventions for this phase

- **SQLite is the default local backend; PostgreSQL is for production.** The storage abstraction must not leak driver-specific syntax. Use SQLAlchemy 2.0 async session consistently so the same code runs against both drivers.
- **Alembic `batch_alter_table` is required for SQLite column changes.** SQLite does not support `ALTER COLUMN` or `DROP COLUMN` directly. Any future migration that modifies an existing column on SQLite must use `with op.batch_alter_table(...)`.
- **All I/O is async.** Use `async def` throughout the storage layer. Subprocess calls (none expected in Phase 2, but noted for later phases) use `asyncio.create_subprocess_exec`, never `subprocess.run`.
- **NetworkX is loaded on demand, not persisted.** Load a bounded subgraph from SQLModel into `nx.DiGraph` only for ego graph / path queries. Do not store a persistent NetworkX graph; it is a query-time projection.
- **orjson for all JSON columns.** Use `orjson.dumps(value).decode()` when writing JSON text columns and `orjson.loads(row.payload_json)` when reading. Do not use `json.dumps` / `json.loads` anywhere in the storage layer.
- **First migration is `0001_initial.py`, not `.sql`.** Alembic migrations are Python scripts. The raw SQL from this plan is reference DDL; the actual migration uses Alembic's `op.create_table` / `op.create_index` API so checksums and down-migration stubs work correctly.

---

## 2. Inputs, Outputs, and Boundaries

### Required Inputs

Phase 2 depends on Phase 1 model contracts:

- Graph node and edge models.
- Repository, snapshot, span, provenance, and artefact references.
- Evidence bundle and verdict models.
- Run record and run event models.
- Harness Condition Sheet model.
- Policy decision, budget event, compaction event, monitor alert, verification event, maintainability result, and prompt/manifest regression result models.
- Incident and promotion candidate models.
- Harness stage, drift finding, AI-readiness report, and readiness history models.
- Supply-chain provenance model.
- Schema versioning and validation helpers.

Phase 2 also assumes the Phase 0 package skeleton has a place for storage code and tests.

### Phase Outputs

Phase 2 should produce:

- A local workspace store abstraction.
- A repository registry.
- A snapshot ledger.
- A graph store.
- A graph query layer.
- A harness metadata store.
- An operational run/evidence store.
- An artefact registry.
- Basic graph export/import.
- Storage migration support.
- Storage tests and fixtures.
- A storage README or design note.

### Non-Goals

Do not implement these in Phase 2:

- File tree scanning.
- Git blame collection.
- Parser or ctags adapters.
- `graph_build` or `graph_update` indexing logic.
- MCP server routes.
- MCP task persistence.
- SARIF parsing.
- Static-analysis execution.
- LLM-generated summaries.
- Vector embeddings.
- Workflow state machines.
- Dynamic traces.
- Memory retrieval or compaction.

The store should be ready for those phases, but it should not perform their work.

---

## 3. Storage Strategy

### Recommended Initial Backend

Use SQLite as the first local persistence backend.

Reasons:

- It is local and dependency-light.
- It supports transactions.
- It is easy to test in temporary directories.
- It supports indexes and JSON text columns.
- It is good enough for correctness-focused MVP storage.
- It can later be replaced or supplemented by DuckDB, a graph database, or a specialized index behind the same repository interfaces.

Recommended SQLite settings:

```text
PRAGMA foreign_keys = ON
PRAGMA journal_mode = WAL
PRAGMA synchronous = NORMAL
PRAGMA busy_timeout = 5000
```

Use strict tables if the selected SQLite version supports them. If not, enforce strictness in Python validators before writes.

### Backend Abstraction

Define storage protocols or interfaces so later performance work can swap implementations.

Recommended boundaries:

- `RepositoryRegistry`
- `SnapshotStore`
- `GraphStore`
- `OperationalStore`
- `HarnessMetadataStore`
- `ArtifactStore`
- `ImportExportService`
- `MigrationManager`

Do not leak raw SQL into indexing, MCP, or workflow code. They should use typed store methods.

### Storage Location

Recommended default:

```text
.llm-sca/
  workspace.db
  artifacts/
  exports/
  locks/
```

If project policy prefers a user cache directory, keep a repo-local pointer or configuration record. The first implementation should support repo-local storage because it is easier to inspect and test.

Privacy rule:

- Local database rows may need absolute paths for local operation.
- Exported artefacts and shared reports should default to redacted or repo-relative paths.

---

## 4. Recommended File Layout

Assuming package name `llm_sca_tooling`:

```text
src/llm_sca_tooling/
  storage/
    __init__.py
    workspace.py
    sqlite.py
    migrations.py
    registry.py
    snapshots.py
    graph_store.py
    graph_queries.py
    operations.py
    harness_store.py
    artifacts.py
    export_import.py
    errors.py
    locks.py
    transactions.py
    ids.py
    paths.py
    diagnostics.py

  storage/migrations/
    0001_initial.sql

tests/
  storage/
    fixtures/
      graph_small.json
      run_record_small.json
      mixed_snapshot_graph.json
    test_workspace_store.py
    test_repository_registry.py
    test_snapshot_store.py
    test_graph_store.py
    test_graph_queries.py
    test_operational_store.py
    test_harness_metadata_store.py
    test_artifact_store.py
    test_export_import.py
    test_migrations.py
    test_transactions.py
```

If the project chooses a different package name or storage directory, preserve the boundaries and tests.

---

## 5. Data Domains

Phase 2 owns these persisted data domains.

### 5.1 Workspace Metadata

Workspace metadata records the local store identity and schema state.

Stores:

- Workspace ID.
- Database format version.
- Active schema versions.
- Created and updated timestamps.
- Storage root.
- Artifact root.
- Default redaction/export policy.
- Last migration applied.

### 5.2 Repository Registry

The registry records which repositories are known to the tool.

Stores:

- Repo ID.
- Display name.
- Local root path.
- Root path hash for redacted references.
- VCS type.
- Remote URL hash.
- Default branch.
- Current branch.
- Registration time.
- Last seen time.
- Active status.
- Index status summary.
- Capabilities.
- Policy scope or path allowlist linkage.

### 5.3 Snapshot Ledger

The snapshot ledger records committed and dirty worktree states.

Stores:

- Snapshot ID.
- Repo ID.
- Git SHA.
- Branch.
- Dirty flag.
- Worktree snapshot ID.
- Index freshness status.
- Captured timestamp.
- Source event/run ID.
- File-state summary.
- Diagnostics.

### 5.4 Graph Store

The graph store records typed graph nodes and edges.

Stores:

- Nodes.
- Edges.
- Node properties.
- Edge properties.
- Provenance.
- Snapshot references.
- Diagnostics.
- Graph manifests and chunk artefacts.

### 5.5 Operational Store

The operational store records run evidence and reviewable workflow state.

Stores:

- Run records.
- Run events.
- Harness Condition Sheets.
- Policy decisions.
- Tool-call events.
- Approval and denial events.
- Budget events.
- Compaction events.
- Verification events.
- Monitor alerts.
- Maintainability oracle results.
- Prompt/manifest regression results.
- Incidents.
- Promotion candidates.
- Operational ledger entries.

### 5.6 Harness Metadata Store

Harness metadata describes the active control plane for a repo or workspace.

Stores:

- Active manifest hashes.
- Effective permission profile.
- Sandbox/runtime descriptor.
- Verification gate versions.
- Dependency/analyser versions.
- Supply-chain provenance records.
- Harness stage assessments.
- Drift findings.
- Readiness reports and score history.

### 5.7 Artifact Registry

The artefact registry stores references to large or external payloads.

Stores:

- Graph chunks.
- Export bundles.
- Logs.
- SARIF files.
- Test outputs.
- Trace files.
- Diffs.
- Reports.
- Summary files.

The registry should store hashes and redaction status. The artefact payload can live on disk.

---

## 6. Workspace Store

### 6.1 Responsibilities

The workspace store initializes and opens local persistence.

Responsibilities:

- Create the storage root.
- Create the SQLite database.
- Apply migrations.
- Verify schema compatibility.
- Expose typed store components.
- Provide transaction helpers.
- Record storage diagnostics.

### 6.2 Workspace Metadata Table

Recommended table:

```sql
CREATE TABLE workspace_metadata (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
```

Recommended keys:

- `workspace_id`
- `storage_version`
- `schema_versions`
- `created_ts`
- `artifact_root`
- `default_redaction_policy`
- `last_migration`

Use JSON values so the metadata table stays small and flexible.

### 6.3 Workspace Initialization API

Recommended methods:

```text
initialize_workspace(path, *, create=True) -> WorkspaceStore
open_workspace(path) -> WorkspaceStore
workspace_status() -> WorkspaceStatus
close() -> None
```

Validation:

- Opening an incompatible future storage version fails with a clear error.
- Missing migration fails before any writes.
- Corrupt metadata produces a diagnostic and blocks writes.

---

## 7. Repository Registry

### 7.1 Purpose

The repository registry is the source of truth for registered repositories. Later MCP and CLI tools should use it for `code-intelligence://repos`, `register_repo`, graph resource lookups, and path-scope policy checks.

### 7.2 Repo Identity

Recommended repo ID generation:

```text
repo_id = "repo:" + stable_slug_or_hash
```

The hash input should include:

- Canonical local root path.
- Remote URL if available.
- Optional user-provided alias.

Do not make repo ID depend on current branch or git SHA.

### 7.3 Repository Table

Recommended table:

```sql
CREATE TABLE repositories (
  repo_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  root_path TEXT NOT NULL,
  root_path_hash TEXT NOT NULL,
  vcs_type TEXT NOT NULL,
  remote_url_hash TEXT,
  default_branch TEXT,
  current_branch TEXT,
  registered_ts TEXT NOT NULL,
  last_seen_ts TEXT NOT NULL,
  active INTEGER NOT NULL,
  index_status TEXT NOT NULL,
  latest_snapshot_id TEXT,
  capabilities_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  UNIQUE(root_path)
);
```

Recommended indexes:

```sql
CREATE INDEX idx_repositories_active ON repositories(active);
CREATE INDEX idx_repositories_name ON repositories(name);
CREATE INDEX idx_repositories_latest_snapshot ON repositories(latest_snapshot_id);
```

### 7.4 Registration API

Recommended methods:

```text
register_repo(path, *, name=None, policy_scope=None) -> RepositoryRecord
unregister_repo(repo_id, *, keep_evidence=True) -> RepositoryRecord
get_repo(repo_id_or_name) -> RepositoryRecord
list_repos(active_only=True) -> list[RepositoryRecord]
update_repo_status(repo_id, status) -> None
set_latest_snapshot(repo_id, snapshot_id) -> None
```

### 7.5 Registration Behavior

Registration should:

- Normalize the path.
- Verify the path exists.
- Detect VCS type, initially `git` or `none`.
- Detect current branch when git is available.
- Hash sensitive path or remote fields for redacted exports.
- Create or update the repository row.
- Attach initial metadata.
- Not index files yet.

### 7.6 Duplicate Handling

Rules:

- Registering the same root path twice should be idempotent.
- Registering a moved repository should require an explicit update or new registration.
- Name collisions are allowed only when lookup uses repo ID or disambiguation is explicit.
- A repo cannot be silently overwritten by another root path.

### 7.7 Repository Status Values

Recommended `index_status` values:

- `not_indexed`
- `indexing`
- `fresh`
- `stale`
- `partial`
- `failed`
- `unknown`

These status values summarize latest graph state. Snapshot-level status remains in the snapshot ledger.

### 7.8 Registry Exit Criteria

Registry work is complete when:

- `register_repo` stores repository metadata.
- Duplicate registration is idempotent.
- Registered repos can be listed and queried.
- Repo lookup works by ID and safely by unique name.
- Local root paths are not required in exported public metadata.
- Latest snapshot linkage can be updated.

---

## 8. Snapshot Ledger

### 8.1 Purpose

The snapshot ledger records the code state for graph facts, operational events, and evidence bundles. It makes stale and mixed-snapshot evidence detectable.

### 8.2 Snapshot Table

Recommended table:

```sql
CREATE TABLE snapshots (
  snapshot_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  git_sha TEXT,
  branch TEXT,
  dirty INTEGER NOT NULL,
  worktree_snapshot_id TEXT,
  index_status TEXT NOT NULL,
  captured_ts TEXT NOT NULL,
  source_run_id TEXT,
  source_event_id TEXT,
  file_state_hash TEXT,
  diagnostics_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);
```

Recommended indexes:

```sql
CREATE INDEX idx_snapshots_repo ON snapshots(repo_id);
CREATE INDEX idx_snapshots_git_sha ON snapshots(repo_id, git_sha);
CREATE INDEX idx_snapshots_worktree ON snapshots(repo_id, worktree_snapshot_id);
CREATE INDEX idx_snapshots_status ON snapshots(repo_id, index_status);
CREATE INDEX idx_snapshots_captured_ts ON snapshots(captured_ts);
```

### 8.3 Snapshot Identity

Recommended ID behavior:

- Clean committed snapshot:
  - stable key: repo ID plus git SHA.
- Dirty worktree snapshot:
  - stable key: repo ID plus git SHA plus file-state hash plus timestamp or monotonic capture ID.

The exact dirty snapshot ID can be generated by Phase 3, but Phase 2 must store it.

### 8.4 Snapshot Status Values

Use Phase 1 snapshot states:

- `fresh`
- `stale`
- `partial`
- `mixed`
- `unknown`

Recommended interpretation:

- `fresh`: graph facts match the current snapshot.
- `stale`: known to be outdated relative to repo state.
- `partial`: some facts exist, but indexing was incomplete.
- `mixed`: query result includes facts from more than one snapshot.
- `unknown`: freshness could not be established.

### 8.5 Snapshot API

Recommended methods:

```text
record_snapshot(snapshot) -> SnapshotRef
get_snapshot(snapshot_id) -> SnapshotRef
get_latest_snapshot(repo_id, *, require_fresh=False) -> SnapshotRef | None
list_snapshots(repo_id, *, status=None, limit=None) -> list[SnapshotRef]
mark_snapshot_status(snapshot_id, status, diagnostics=None) -> None
detect_mixed_snapshots(snapshot_ids) -> SnapshotMixResult
```

### 8.6 Mixed-Snapshot Detection

A query result is mixed when:

- It includes more than one `git_sha` for the same repo.
- It includes clean and dirty snapshots for the same repo.
- It includes more than one `worktree_snapshot_id` for the same repo.
- It includes any fact with `index_status=mixed`.
- It joins graph facts with operational evidence from incompatible snapshots without explicit provenance.

The store should return snapshot consistency metadata with graph query results.

### 8.7 Snapshot Exit Criteria

Snapshot work is complete when:

- Clean and dirty snapshots can be recorded.
- Dirty worktree snapshots preserve `worktree_snapshot_id`.
- Latest snapshot can be fetched.
- Stale and partial status can be represented.
- Mixed-snapshot query results are detectable.

---

## 9. Graph Store

### 9.1 Purpose

The graph store persists Phase 1 `GraphNode` and `GraphEdge` objects and provides primitive graph queries for later indexing, MCP, localization, SARIF, repo-QA, and blast-radius phases.

### 9.2 Storage Model

Use normalized columns for common lookup fields and JSON for the validated full payload.

This gives:

- Fast lookup by ID, type, repo, snapshot, file, span, and edge endpoints.
- Full fidelity for schema-defined payloads.
- Simple migration path while schemas are still evolving.

### 9.3 Graph Nodes Table

Recommended table:

```sql
CREATE TABLE graph_nodes (
  node_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
  node_type TEXT NOT NULL,
  label TEXT NOT NULL,
  qualified_name TEXT,
  file_path TEXT,
  start_line INTEGER,
  end_line INTEGER,
  confidence REAL NOT NULL,
  derivation TEXT NOT NULL,
  evidence_strength TEXT NOT NULL,
  provenance_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
```

Recommended indexes:

```sql
CREATE INDEX idx_graph_nodes_repo_snapshot ON graph_nodes(repo_id, snapshot_id);
CREATE INDEX idx_graph_nodes_type ON graph_nodes(repo_id, node_type);
CREATE INDEX idx_graph_nodes_file ON graph_nodes(repo_id, snapshot_id, file_path);
CREATE INDEX idx_graph_nodes_qualified_name ON graph_nodes(repo_id, qualified_name);
CREATE INDEX idx_graph_nodes_span ON graph_nodes(repo_id, file_path, start_line, end_line);
CREATE INDEX idx_graph_nodes_derivation ON graph_nodes(derivation);
```

### 9.4 Graph Edges Table

Recommended table:

```sql
CREATE TABLE graph_edges (
  edge_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
  edge_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  confidence REAL NOT NULL,
  derivation TEXT NOT NULL,
  evidence_strength TEXT NOT NULL,
  provenance_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL,
  FOREIGN KEY(source_id) REFERENCES graph_nodes(node_id),
  FOREIGN KEY(target_id) REFERENCES graph_nodes(node_id)
);
```

Recommended indexes:

```sql
CREATE INDEX idx_graph_edges_repo_snapshot ON graph_edges(repo_id, snapshot_id);
CREATE INDEX idx_graph_edges_type ON graph_edges(repo_id, edge_type);
CREATE INDEX idx_graph_edges_source ON graph_edges(source_id);
CREATE INDEX idx_graph_edges_target ON graph_edges(target_id);
CREATE INDEX idx_graph_edges_source_type ON graph_edges(source_id, edge_type);
CREATE INDEX idx_graph_edges_target_type ON graph_edges(target_id, edge_type);
```

### 9.5 Graph Diagnostics Table

Recommended table:

```sql
CREATE TABLE graph_diagnostics (
  diagnostic_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  snapshot_id TEXT REFERENCES snapshots(snapshot_id),
  severity TEXT NOT NULL,
  code TEXT NOT NULL,
  message TEXT NOT NULL,
  affected_node_ids_json TEXT NOT NULL,
  affected_edge_ids_json TEXT NOT NULL,
  provenance_json TEXT,
  created_ts TEXT NOT NULL
);
```

### 9.6 Graph Manifest Table

A full graph resource must later be served as a manifest plus chunks, not as an unconditional full dump.

Recommended table:

```sql
CREATE TABLE graph_manifests (
  graph_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
  node_count INTEGER NOT NULL,
  edge_count INTEGER NOT NULL,
  chunk_artifact_ids_json TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  generated_ts TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
```

### 9.7 Write API

Recommended methods:

```text
add_node(node) -> GraphNode
add_nodes(nodes) -> StoreWriteResult
add_edge(edge) -> GraphEdge
add_edges(edges) -> StoreWriteResult
upsert_node(node) -> GraphNode
upsert_edge(edge) -> GraphEdge
delete_nodes_for_snapshot(repo_id, snapshot_id, *, node_types=None) -> DeleteResult
delete_edges_for_snapshot(repo_id, snapshot_id, *, edge_types=None) -> DeleteResult
record_graph_diagnostic(diagnostic) -> GraphDiagnostic
record_graph_manifest(manifest) -> GraphManifest
```

### 9.8 Write Rules

Rules:

- Validate Phase 1 schema objects before writing.
- Writes should be transactional by batch.
- Edge writes require existing endpoints unless explicitly using deferred mode inside one transaction.
- Node and edge rows should store both selected indexed fields and full JSON payload.
- Duplicate ID writes should be idempotent only when payload hash matches.
- Duplicate ID with different payload should fail unless caller explicitly uses update/upsert.
- Deleting a snapshot's nodes should remove or reject dependent edges according to explicit policy.

### 9.9 Query API

Required primitives from the source plan:

```text
fetch_node(node_id) -> GraphNode | None
fetch_edge(edge_id) -> GraphEdge | None
fetch_by_id(id) -> GraphNode | GraphEdge | None
fetch_nodes_by_type(repo_id, node_type, *, snapshot_id=None) -> list[GraphNode]
fetch_edges_by_type(repo_id, edge_type, *, snapshot_id=None) -> list[GraphEdge]
fetch_neighbours(node_id, *, direction="both", edge_types=None, depth=1) -> GraphNeighbourResult
fetch_ego_graph(node_ids, *, depth=1, edge_types=None, node_types=None, limit=None) -> GraphSlice
fetch_by_file(repo_id, file_path, *, snapshot_id=None) -> GraphSlice
fetch_by_span(repo_id, file_path, start_line, end_line, *, snapshot_id=None) -> GraphSlice
```

Recommended additional primitives:

```text
find_symbols(repo_id, qualified_name=None, file_path=None, snapshot_id=None) -> list[GraphNode]
find_edges_between(source_id, target_id, edge_type=None) -> list[GraphEdge]
count_nodes(repo_id, snapshot_id=None) -> int
count_edges(repo_id, snapshot_id=None) -> int
graph_status(repo_id, snapshot_id=None) -> GraphStoreStatus
```

### 9.10 Graph Slice Result

A graph query should return more than a list of nodes and edges.

Recommended result:

```text
GraphSlice
  repo_id
  requested_snapshot_id
  snapshot_ids
  snapshot_consistency
  nodes
  edges
  diagnostics
  truncated
  limit
  provenance_summary
```

Rules:

- Every graph slice must include snapshot IDs.
- Mixed snapshots must be reported.
- Truncated results must be explicit.
- Provenance and confidence must remain in each node and edge payload.

### 9.11 Query Safety

The graph store should prevent accidental unbounded reads.

Rules:

- `fetch_ego_graph` should accept a limit.
- Queries with no repo ID should be rejected except admin diagnostics.
- Full graph export should use manifests and chunks.
- Slice queries should return truncation metadata instead of silently dropping data.
- Later LLM-facing code should never receive graph data without snapshot and provenance metadata.

### 9.12 Graph Store Exit Criteria

Graph store work is complete when:

- Graph facts can be added and queried.
- Fetch by ID, type, file/span, neighbours, and ego graph work on fixtures.
- Edge endpoint integrity is enforced.
- Provenance and snapshot fields survive round trips.
- Mixed-snapshot graph slices are detectable.
- Basic graph export/import can preserve graph content.

---

## 10. Harness Metadata Store

### 10.1 Purpose

The harness metadata store records the current operating envelope for repositories and workflows. Later Phase 4A logic will use this data for policy checks, operational review, readiness audits, and release gates.

### 10.2 Tables

Recommended table for harness state:

```sql
CREATE TABLE harness_metadata (
  metadata_id TEXT PRIMARY KEY,
  repo_id TEXT REFERENCES repositories(repo_id),
  kind TEXT NOT NULL,
  active INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
```

Recommended `kind` values:

- `manifest_hashes`
- `permission_profile`
- `sandbox_runtime`
- `verification_gate_versions`
- `dependency_versions`
- `analyser_versions`
- `effective_policy`
- `manifest_state`

Recommended table for supply-chain provenance:

```sql
CREATE TABLE supply_chain_records (
  supply_chain_record_id TEXT PRIMARY KEY,
  repo_id TEXT REFERENCES repositories(repo_id),
  component_type TEXT NOT NULL,
  name TEXT NOT NULL,
  version TEXT,
  source TEXT,
  hash TEXT,
  payload_json TEXT NOT NULL,
  captured_ts TEXT NOT NULL
);
```

### 10.3 Harness Metadata API

Recommended methods:

```text
put_harness_metadata(repo_id, kind, payload, *, active=True) -> HarnessMetadataRecord
get_harness_metadata(repo_id, kind, *, active_only=True) -> list[HarnessMetadataRecord]
record_supply_chain_record(record) -> SupplyChainRecord
list_supply_chain_records(repo_id=None, component_type=None) -> list[SupplyChainRecord]
```

### 10.4 Rules

- Active harness metadata should be versioned by hash.
- Older records should remain queryable.
- Effective policy and manifest state should be tied to repo and timestamp.
- Supply-chain records should support workspace-level and repo-level components.
- Storage should not decide whether a policy passes. It only records and retrieves typed state.

---

## 11. Operational Store

### 11.1 Purpose

The operational store persists the append-only run evidence needed for operational review, trace replay, incident response, promotion review, and release gates.

### 11.2 Run Records Table

Recommended table:

```sql
CREATE TABLE run_records (
  run_id TEXT PRIMARY KEY,
  workflow TEXT NOT NULL,
  user_intent_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  start_ts TEXT NOT NULL,
  end_ts TEXT,
  toolset_hash TEXT NOT NULL,
  policy_id TEXT NOT NULL,
  permission_profile TEXT NOT NULL,
  harness_condition_id TEXT,
  final_verdict_id TEXT,
  run_event_count INTEGER NOT NULL,
  redaction_policy_json TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
```

Recommended join table:

```sql
CREATE TABLE run_repositories (
  run_id TEXT NOT NULL REFERENCES run_records(run_id),
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  PRIMARY KEY(run_id, repo_id)
);
```

Recommended indexes:

```sql
CREATE INDEX idx_run_records_workflow ON run_records(workflow);
CREATE INDEX idx_run_records_status ON run_records(status);
CREATE INDEX idx_run_records_start_ts ON run_records(start_ts);
CREATE INDEX idx_run_repositories_repo ON run_repositories(repo_id);
```

### 11.3 Run Events Table

Recommended table:

```sql
CREATE TABLE run_events (
  event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES run_records(run_id),
  seq INTEGER NOT NULL,
  ts TEXT NOT NULL,
  type TEXT NOT NULL,
  actor TEXT NOT NULL,
  stage TEXT NOT NULL,
  policy_action TEXT,
  redaction_status TEXT NOT NULL,
  token_count INTEGER,
  wall_ms INTEGER,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  UNIQUE(run_id, seq)
);
```

Recommended indexes:

```sql
CREATE INDEX idx_run_events_run ON run_events(run_id, seq);
CREATE INDEX idx_run_events_type ON run_events(type);
CREATE INDEX idx_run_events_stage ON run_events(stage);
CREATE INDEX idx_run_events_ts ON run_events(ts);
CREATE INDEX idx_run_events_policy_action ON run_events(policy_action);
```

### 11.4 Harness Condition Table

Recommended table:

```sql
CREATE TABLE harness_conditions (
  harness_condition_id TEXT PRIMARY KEY,
  run_id TEXT REFERENCES run_records(run_id),
  toolset_hash TEXT NOT NULL,
  permission_profile TEXT NOT NULL,
  captured_ts TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
```

### 11.5 Operational Event Tables

The first implementation can store specialized event payloads as JSON rows with indexed common fields.

Recommended generic table:

```sql
CREATE TABLE operational_records (
  record_id TEXT PRIMARY KEY,
  repo_id TEXT REFERENCES repositories(repo_id),
  run_id TEXT REFERENCES run_records(run_id),
  event_id TEXT REFERENCES run_events(event_id),
  kind TEXT NOT NULL,
  status TEXT,
  policy_action TEXT,
  severity TEXT,
  incident_id TEXT,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL
);
```

Recommended `kind` values:

- `policy_decision`
- `tool_call`
- `approval`
- `budget_event`
- `compaction_event`
- `verification_event`
- `monitor_alert`
- `maintainability_oracle`
- `manifest_regression`
- `readiness_report`
- `promotion_candidate`

Recommended indexes:

```sql
CREATE INDEX idx_operational_records_repo ON operational_records(repo_id);
CREATE INDEX idx_operational_records_run ON operational_records(run_id);
CREATE INDEX idx_operational_records_kind ON operational_records(kind);
CREATE INDEX idx_operational_records_incident ON operational_records(incident_id);
CREATE INDEX idx_operational_records_created_ts ON operational_records(created_ts);
CREATE INDEX idx_operational_records_policy_action ON operational_records(policy_action);
```

### 11.6 Incident Table

Recommended table:

```sql
CREATE TABLE incidents (
  incident_id TEXT PRIMARY KEY,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  title TEXT NOT NULL,
  primary_repo_id TEXT REFERENCES repositories(repo_id),
  opened_ts TEXT NOT NULL,
  closed_ts TEXT,
  payload_json TEXT NOT NULL
);
```

Recommended join tables:

```sql
CREATE TABLE incident_runs (
  incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
  run_id TEXT NOT NULL REFERENCES run_records(run_id),
  PRIMARY KEY(incident_id, run_id)
);

CREATE TABLE incident_events (
  incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
  event_id TEXT NOT NULL REFERENCES run_events(event_id),
  PRIMARY KEY(incident_id, event_id)
);
```

### 11.7 Promotion Records Table

Recommended table:

```sql
CREATE TABLE promotion_records (
  promotion_id TEXT PRIMARY KEY,
  source_run_id TEXT NOT NULL REFERENCES run_records(run_id),
  target_type TEXT NOT NULL,
  review_state TEXT NOT NULL,
  owner TEXT,
  expires_ts TEXT,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
```

### 11.8 Readiness Reports Table

Recommended table:

```sql
CREATE TABLE readiness_reports (
  readiness_report_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  stage TEXT NOT NULL,
  total_score INTEGER NOT NULL,
  threshold_status TEXT NOT NULL,
  no_regression_status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL
);
```

Recommended indexes:

```sql
CREATE INDEX idx_readiness_reports_repo ON readiness_reports(repo_id, created_ts);
CREATE INDEX idx_readiness_reports_stage ON readiness_reports(stage);
```

### 11.9 Operational Store API

Recommended methods:

```text
create_run(run_record) -> RunRecord
append_run_event(run_id, event) -> RunEvent
get_run(run_id, *, include_events=False) -> RunRecordView
list_run_events(run_id, *, type=None, stage=None, after_seq=None) -> list[RunEvent]
close_run(run_id, status, *, final_verdict_id=None, end_ts=None) -> RunRecord
record_harness_condition(condition) -> HarnessCondition
get_harness_condition(harness_condition_id) -> HarnessCondition
record_operational_record(record) -> OperationalRecord
query_operational_records(repo_id=None, run_id=None, kind=None, time_range=None) -> list[OperationalRecord]
record_incident(incident) -> Incident
get_incident(incident_id) -> Incident
query_incidents(repo_id=None, status=None, severity=None, time_range=None) -> list[Incident]
record_promotion_candidate(candidate) -> PromotionCandidate
query_promotion_candidates(source_run_id=None, target_type=None, review_state=None) -> list[PromotionCandidate]
record_readiness_report(report) -> AIReadinessReport
query_readiness_reports(repo_id, *, limit=None) -> list[AIReadinessReport]
```

### 11.10 Append-Only Event Rules

Rules:

- `append_run_event` is the only way to add run events.
- Updating a run event is forbidden except for explicit repair tooling that writes a correction event instead.
- `seq` must be monotonic per run.
- Duplicate `seq` fails.
- Mismatched `run_id` fails.
- Redaction status is required.
- Denied actions are stored like allowed actions.
- Budget hard stops are stored before the run is marked blocked or unknown.

### 11.11 Operational Query Requirements

Phase 2 must support these queries:

- Runs by repo.
- Runs by workflow.
- Runs by status.
- Runs by time range.
- Run events by type and stage.
- Runs linked to incidents.
- Incidents by repo.
- Incidents by status or severity.
- Incidents by source run/event.
- Promotion records by source run and review state.
- Readiness reports by repo and time.

These directly support the source-plan exit criterion:

```text
Run records can be queried by repo, workflow, status, incident type, and time.
```

### 11.12 Operational Store Exit Criteria

Operational store work is complete when:

- A run record can be created, appended to, queried, and closed.
- Run events are append-only and sequence-numbered.
- Harness Condition Sheets can be linked to runs.
- Policy, budget, compaction, verification, monitor, and review records can be stored.
- Incidents and promotion records retain links to source run events and artefacts.
- Runs can be queried by repo, workflow, status, incident type, and time.

---

## 12. Artifact Registry

### 12.1 Purpose

The artifact registry tracks large or externally useful payloads without bloating graph and run event rows.

### 12.2 Artifact Table

Recommended table:

```sql
CREATE TABLE artifacts (
  artifact_id TEXT PRIMARY KEY,
  repo_id TEXT REFERENCES repositories(repo_id),
  run_id TEXT REFERENCES run_records(run_id),
  kind TEXT NOT NULL,
  uri TEXT NOT NULL,
  sha256 TEXT,
  size_bytes INTEGER,
  media_type TEXT,
  redaction_status TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);
```

Recommended indexes:

```sql
CREATE INDEX idx_artifacts_repo ON artifacts(repo_id);
CREATE INDEX idx_artifacts_run ON artifacts(run_id);
CREATE INDEX idx_artifacts_kind ON artifacts(kind);
CREATE INDEX idx_artifacts_sha256 ON artifacts(sha256);
```

### 12.3 Artifact API

Recommended methods:

```text
record_artifact(ref, *, payload_path=None) -> ArtifactRef
get_artifact(artifact_id) -> ArtifactRef
list_artifacts(repo_id=None, run_id=None, kind=None) -> list[ArtifactRef]
verify_artifact_hash(artifact_id) -> ArtifactHashResult
```

### 12.4 Rules

- Artefacts require redaction status.
- Hashes are required for release or evaluation evidence.
- Missing artefact files should produce diagnostics, not silent success.
- Public exports should include hash and metadata but not necessarily payload.

---

## 13. Basic Export And Import

### 13.1 Purpose

Export/import lets tests, operational reviews, and later MCP resources move graph and operational evidence without depending on the internal SQLite shape.

### 13.2 Export Types

Recommended export types:

- `graph_snapshot`
- `graph_slice`
- `repo_registry`
- `run_record`
- `operational_bundle`
- `readiness_bundle`
- `incident_bundle`
- `workspace_metadata`

### 13.3 Export Format

Recommended bundle structure:

```text
export.json
artifacts/
  ...
```

Recommended export metadata:

```text
ExportBundle
  export_id
  export_type
  created_ts
  schema_versions
  storage_version
  repos
  snapshots
  payload
  artifact_refs
  redaction_policy
  diagnostics
```

### 13.4 Export API

Recommended methods:

```text
export_graph(repo_id, snapshot_id, destination, *, include_artifacts=False) -> ExportBundle
export_graph_slice(slice, destination, *, include_artifacts=False) -> ExportBundle
export_run(run_id, destination, *, include_artifacts=False) -> ExportBundle
export_workspace_summary(destination) -> ExportBundle
import_bundle(path, *, mode="validate_then_insert") -> ImportResult
validate_bundle(path) -> BundleValidationResult
```

### 13.5 Import Rules

Rules:

- Validate schema versions before insert.
- Validate payloads against Phase 1 models.
- Preserve original IDs unless conflict policy says otherwise.
- Detect duplicate payload hash conflicts.
- Imported public bundles should not require absolute local paths.
- Import should run inside a transaction.

### 13.6 Export/Import Exit Criteria

Export/import work is complete when:

- A graph fixture can be exported and re-imported into an empty store.
- A run record bundle can be exported and validated.
- Hash mismatches fail import.
- Schema incompatibility fails clearly.
- Redaction metadata survives export/import.

---

## 14. Transactions, Locking, And Concurrency

### 14.1 Transaction Rules

Use transactions for:

- Repository registration.
- Snapshot recording plus status update.
- Batch node/edge writes.
- Run creation.
- Run event append.
- Run close.
- Incident creation plus links.
- Import bundle insertion.

Recommended helper:

```text
with store.transaction("reason"):
    ...
```

### 14.2 Atomicity Requirements

Rules:

- A batch graph write either fully commits or fully rolls back.
- A run event append either writes the event and updates run count or writes neither.
- Incident creation writes incident and source links together.
- Import writes all rows or none.

### 14.3 Locking

SQLite WAL handles basic concurrent readers. For writers:

- Use short transactions.
- Avoid holding write transactions across expensive validation or file hashing.
- Validate payloads before opening a write transaction where possible.
- Use a workspace lock file only for operations that mutate storage layout, such as migrations.

### 14.4 Failure Behavior

Rules:

- Database errors should raise typed storage errors.
- Partial writes should not remain after a failed transaction.
- Corrupt JSON payload should be detected on read and surfaced as a diagnostic.
- Migration failure should leave the previous database usable or create a backup first.

---

## 15. Migrations

### 15.1 Migration Table

Recommended table:

```sql
CREATE TABLE schema_migrations (
  version TEXT PRIMARY KEY,
  applied_ts TEXT NOT NULL,
  checksum TEXT NOT NULL,
  description TEXT NOT NULL
);
```

### 15.2 Migration Rules

Rules:

- Every schema migration has a version, checksum, and description.
- Migrations run inside transactions when SQLite supports it for the operation.
- Migration checksums are verified before applying later migrations.
- Downgrade is not required in Phase 2, but backup before migration is recommended.
- Incompatible storage version should fail before writes.

### 15.3 Initial Migration

`0001_initial.sql` should create:

- `workspace_metadata`
- `repositories`
- `snapshots`
- `graph_nodes`
- `graph_edges`
- `graph_diagnostics`
- `graph_manifests`
- `harness_metadata`
- `supply_chain_records`
- `run_records`
- `run_repositories`
- `run_events`
- `harness_conditions`
- `operational_records`
- `incidents`
- `incident_runs`
- `incident_events`
- `promotion_records`
- `readiness_reports`
- `artifacts`
- `schema_migrations`

### 15.4 Migration Tests

Required tests:

- New workspace applies initial migration.
- Re-opening workspace does not reapply migration.
- Migration checksum mismatch fails.
- Unknown future migration fails safely.
- Database remains readable after failed migration setup.

---

## 16. Storage Errors And Diagnostics

### 16.1 Error Types

Recommended exceptions:

- `StorageError`
- `WorkspaceNotFoundError`
- `WorkspaceIncompatibleError`
- `MigrationError`
- `RepositoryNotFoundError`
- `DuplicateRepositoryError`
- `SnapshotNotFoundError`
- `GraphIntegrityError`
- `GraphQueryLimitError`
- `RunNotFoundError`
- `RunEventSequenceError`
- `ArtifactNotFoundError`
- `ImportExportError`
- `ValidationStorageError`

### 16.2 Diagnostic Records

Storage diagnostics should be typed and, where relevant, storable as operational records.

Examples:

- Missing artefact file.
- Orphaned edge detected.
- Snapshot status conflict.
- Schema version mismatch.
- Import skipped due to conflict.
- Query truncated due to limit.
- Mixed snapshot detected.

---

## 17. Query Result Contracts

### 17.1 Store Results Should Include Diagnostics

Query results that may be incomplete or risky should include diagnostics, not only payloads.

Recommended result metadata:

- `truncated`
- `limit`
- `snapshot_consistency`
- `diagnostics`
- `query_time_ms`
- `source_store_version`

### 17.2 Graph Query Metadata

Graph query results must include:

- Requested repo.
- Requested snapshot if any.
- Actual snapshot IDs included.
- Snapshot consistency.
- Node count.
- Edge count.
- Truncation status.

### 17.3 Operational Query Metadata

Operational query results should include:

- Filters applied.
- Result count.
- Time range.
- Whether events were included.
- Whether linked artefacts were resolved.

---

## 18. Security, Privacy, And Redaction

### 18.1 Local Storage Policy

Local storage may contain sensitive repository metadata. Store design should make redaction explicit.

Rules:

- Redaction status is required for artefacts.
- Run events must preserve redaction status.
- Export should default to redacted paths and hashed remote URLs.
- Raw command output should be an artefact with redaction status, not inline event prose.
- Absolute paths should be absent from public exports by default.

### 18.2 Secrets And PII

Phase 2 does not implement secret scanning, but it must preserve fields for later secret/redaction checks.

Storage should support:

- `redaction_status`.
- `redaction_policy`.
- Hash-only artefact refs.
- Blocked artefact refs.
- Incident links for secret or redaction failures.

### 18.3 Policy Enforcement Boundary

Phase 2 stores policy decisions. It does not decide them.

Later phases implement:

- Tool policy evaluation.
- Path allowlist decisions.
- Network policy decisions.
- Approval requirements.

Phase 2 must make those decisions persistable and queryable.

---

## 19. Performance Boundaries

Phase 2 is correctness-first. Still, define practical limits so tests catch accidental unbounded behavior.

Recommended initial defaults:

- Max graph slice nodes: 2,000.
- Max graph slice edges: 5,000.
- Max run events returned by default: 1,000.
- Max artifact inline preview: 0 bytes by default.
- Full graph export requires explicit call.

Rules:

- Limits should be configurable.
- Query truncation must be explicit.
- Store APIs should avoid returning unbounded full graphs accidentally.
- Large graph resources should later use manifests and chunk artefacts.

---

## 20. Test Plan

### 20.1 Workspace Tests

Required tests:

- New workspace initializes successfully.
- Existing workspace opens without changing metadata.
- Workspace status reports storage version and schema versions.
- Incompatible future version fails.
- Missing migration fails clearly.

### 20.2 Repository Registry Tests

Required tests:

- `register_repo` stores repository metadata.
- Registering the same path twice is idempotent.
- Registering two different repos with the same display name requires ID disambiguation.
- Listing active repositories works.
- Unregister with `keep_evidence=True` keeps graph and run rows.
- Latest snapshot linkage can be updated.
- Public export metadata redacts local path and remote URL.

### 20.3 Snapshot Tests

Required tests:

- Clean snapshot with `git_sha` is stored.
- Dirty snapshot with `worktree_snapshot_id` is stored.
- Snapshot status can be marked stale, partial, mixed, and unknown.
- Latest snapshot can be fetched.
- Mixed snapshot detection identifies multiple snapshot IDs for same repo.
- Snapshot diagnostics survive round trip.

### 20.4 Graph Store Tests

Required tests:

- Node insert and fetch by ID.
- Edge insert and fetch by ID.
- Edge insert fails when endpoint does not exist.
- Batch insert rolls back on invalid edge.
- Fetch nodes by type.
- Fetch edges by type.
- Fetch neighbours.
- Fetch ego graph.
- Fetch by file.
- Fetch by span.
- Query limit produces explicit truncation.
- Mixed-snapshot slice reports mixed status.
- Node and edge JSON payloads round-trip through Phase 1 models.

### 20.5 Harness Metadata Tests

Required tests:

- Active manifest hash record can be stored and fetched.
- Permission profile record can be stored and fetched.
- Verification gate versions can be stored.
- Supply-chain provenance records can be listed by component type.
- Older metadata records remain queryable.

### 20.6 Operational Store Tests

Required tests:

- Run record can be created.
- Run event append increments event count.
- Duplicate event sequence fails.
- Event with mismatched run ID fails.
- Run can be closed.
- Harness Condition Sheet links to run.
- Policy decision record can be stored.
- Budget event record can be stored.
- Monitor alert record can be stored.
- Incident links to source run and event.
- Promotion candidate links to source run.
- Readiness report can be stored and queried.
- Runs can be queried by repo, workflow, status, incident type, and time.

### 20.7 Artifact Tests

Required tests:

- Artefact record stores hash, size, media type, and redaction status.
- Missing artefact file produces diagnostic.
- Hash verification passes for matching payload.
- Hash verification fails for modified payload.
- Listing artefacts by repo, run, and kind works.

### 20.8 Export/Import Tests

Required tests:

- Graph export validates against Phase 1 graph schema.
- Graph export can be imported into empty workspace.
- Run export includes run record, events, harness condition, and artefact refs.
- Import rejects incompatible schema version.
- Import rejects hash mismatch.
- Import transaction rolls back on conflict.
- Redaction metadata survives export/import.

### 20.9 Transaction Tests

Required tests:

- Failed graph batch leaves no partial nodes or edges.
- Failed run event append does not increment event count.
- Failed incident creation does not leave orphan links.
- Failed import leaves target store unchanged.

---

## 21. Work Packages

### P2.1 Storage Backend And Workspace Initialization

Build:

- SQLite connection manager.
- Workspace root creation.
- Metadata table.
- Migration runner.
- Transaction helper.
- Typed storage errors.

Deliverables:

- `storage/workspace.py`
- `storage/sqlite.py`
- `storage/migrations.py`
- `storage/migrations/0001_initial.sql`
- Workspace tests.

Acceptance:

- New workspace can be initialized and reopened.
- Migrations are applied exactly once.
- Storage metadata is queryable.

### P2.2 Repository Registry

Build:

- Repository table.
- Path normalization.
- Repo ID generation.
- Registration, lookup, list, unregister, and status update APIs.
- Redacted export view for repository metadata.

Deliverables:

- `storage/registry.py`
- Registry tests.

Acceptance:

- `register_repo` stores repository metadata.
- Duplicate registration is idempotent.
- Repo listing supports the future `code-intelligence://repos` resource.

### P2.3 Snapshot Ledger

Build:

- Snapshot table.
- Snapshot record/fetch/list APIs.
- Latest snapshot handling.
- Snapshot status updates.
- Mixed-snapshot detection helper.

Deliverables:

- `storage/snapshots.py`
- Snapshot tests.

Acceptance:

- Dirty worktree snapshots are represented.
- Mixed-snapshot queries are detectable.
- Snapshot provenance survives storage round trip.

### P2.4 Graph Store Writes

Build:

- Node table.
- Edge table.
- Diagnostics table.
- Manifest table.
- Add/upsert/batch methods.
- Endpoint integrity checks.
- Payload hash or equality check for duplicate IDs.

Deliverables:

- `storage/graph_store.py`
- Graph write tests.

Acceptance:

- Graph facts can be added.
- Invalid edges fail.
- Batch writes are transactional.

### P2.5 Graph Query Primitives

Build:

- Fetch by ID.
- Fetch by type.
- Fetch neighbours.
- Fetch ego graph.
- Fetch by file/span.
- Query result metadata.
- Truncation and mixed-snapshot diagnostics.

Deliverables:

- `storage/graph_queries.py`
- Query tests.

Acceptance:

- Required graph query primitives pass fixture tests.
- Graph slices include snapshot consistency metadata.

### P2.6 Artifact Registry

Build:

- Artifact table.
- Record/get/list APIs.
- Hash verification.
- Missing-file diagnostics.

Deliverables:

- `storage/artifacts.py`
- Artifact tests.

Acceptance:

- Large payloads can be referenced by ID and hash.
- Redaction status is persisted.

### P2.7 Harness Metadata Store

Build:

- Harness metadata table.
- Supply-chain records table.
- Store/fetch/list APIs.

Deliverables:

- `storage/harness_store.py`
- Harness metadata tests.

Acceptance:

- Active manifest hashes, permission profile, sandbox/runtime descriptor, verification gate versions, and dependency/analyser versions can be stored.

### P2.8 Operational Store

Build:

- Run records table.
- Run repository join table.
- Run events table.
- Harness conditions table.
- Operational records table.
- Incidents, incident links, promotion records, readiness reports.
- Run/event/incident/promotion/readiness query APIs.

Deliverables:

- `storage/operations.py`
- Operational store tests.

Acceptance:

- Run records can be queried by repo, workflow, status, incident type, and time.
- Incidents and promotion records retain links to source run events and artefacts.

### P2.9 Export And Import

Build:

- Export bundle model if not already in Phase 1.
- Graph export.
- Run export.
- Workspace summary export.
- Bundle validation.
- Import into empty workspace.

Deliverables:

- `storage/export_import.py`
- Export/import tests.

Acceptance:

- Basic graph export/import works.
- Run record export validates and preserves links.

### P2.10 Documentation And Diagnostics

Build:

- Storage README.
- Database layout notes.
- Query API notes.
- Snapshot consistency notes.
- Redaction/export notes.

Deliverables:

- `docs/storage.md` or equivalent.
- Storage diagnostic examples.

Acceptance:

- Later Phase 3 and Phase 4 work can consume the store without reading SQL internals.

---

## 22. Suggested Implementation Order

Recommended order:

1. Storage errors and transaction helper.
2. SQLite workspace initialization.
3. Initial migration.
4. Repository registry.
5. Snapshot ledger.
6. Artifact registry.
7. Graph node/edge writes.
8. Graph query primitives.
9. Harness metadata store.
10. Operational store.
11. Export/import.
12. Documentation.

Reasoning:

- Registry and snapshots are prerequisites for graph facts.
- Artifact registry helps avoid stuffing large payloads into operational rows.
- Graph writes should land before graph queries.
- Operational store can be implemented once run and artifact references are ready.
- Export/import is easiest once all core stores exist.

---

## 23. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 2 |
|---|---|
| Phase 3 - Repository indexing MVP | Repository registry, snapshot ledger, graph writes, graph diagnostics, graph manifests, artifact refs |
| Phase 4 - MCP server core | Repo listing, graph manifests, graph slices, schema-backed reads, resource freshness data |
| Phase 4A - Operational runtime plane | Run store, event store, harness conditions, policy/budget/monitor records, incidents, readiness, promotions |
| Phase 5 - Language backend expansion | Batch graph writes, backend diagnostics, capability metadata, snapshot-aware updates |
| Phase 6 - SARIF/static analysis | Artifact registry, SARIF alert node storage, `warned_by` edge storage, SARIF run records |
| Phase 7 - Interface plugins | Interface node/edge storage, plugin capability metadata, graph traversal |
| Phase 8 - Repo-QA | Graph slice retrieval, file/symbol lookups, snapshot consistency metadata |
| Phase 9 - Fault localisation | Neighbour/ego graph queries, file/span fetches, evidence freshness checks |
| Phase 10 - Evaluation harness | Eval run records, harness condition storage, artifact registry, readiness and operational metrics |
| Phase 11 - Patch review | Run events, verification events, SARIF/test delta artifact refs, graph context queries |
| Phase 12 - SAST repair | Alert-linked graph nodes, artifact registry, run and verification evidence |
| Phase 13 - Bug-resolve | Full operational run records, graph slices, incidents, promotion candidates |
| Phase 14 - Implementation-check | Document/spec graph nodes, contract artefact storage, clause verdict evidence, snapshot checks |
| Phase 15 - Blast radius | Ego graph traversal, interface edges, cross-repo graph query foundation |
| Phase 16 - Dynamic traces | Trace artefact refs, runtime trace nodes, observed-in edges |
| Phase 17 - Memory | Promotion records, trajectory references, graph-memory linked source runs |
| Phase 18 - Release gates | Stored operational metrics, readiness reports, incidents, harness conditions, exportable evidence |
| Phase 19 - Distribution | Migrations, export/delete support, large graph chunking, retention diagnostics |

---

## 24. Exit Criteria Mapping

Source Phase 2 exit criterion:

- `register_repo` stores repository metadata.

Concrete acceptance:

- Repository row is created with repo ID, root path, path hash, VCS type, branch metadata, registration timestamps, active status, and index status.
- Re-registering the same repo is idempotent.

Source Phase 2 exit criterion:

- Graph facts can be added and queried.

Concrete acceptance:

- Nodes and edges can be inserted, fetched by ID, fetched by type, fetched by file/span, and traversed by neighbour/ego graph.
- Edge endpoint integrity is enforced.

Source Phase 2 exit criterion:

- Dirty worktree snapshots are represented.

Concrete acceptance:

- Snapshot table stores `dirty=true` and `worktree_snapshot_id`.
- Graph facts can reference dirty snapshots.

Source Phase 2 exit criterion:

- Mixed-snapshot queries are detectable.

Concrete acceptance:

- Graph slice result includes all snapshot IDs and `snapshot_consistency`.
- Query helper flags multiple incompatible snapshot IDs for the same repo.

Source Phase 2 exit criterion:

- Stored evidence can be tied back to the harness condition under which it was produced.

Concrete acceptance:

- Run records link to Harness Condition Sheets.
- Graph, artifact, and operational records can reference source run/event IDs through provenance or explicit fields.

Source Phase 2 exit criterion:

- Run records can be queried by repo, workflow, status, incident type, and time.

Concrete acceptance:

- Indexed query methods exist and are covered by tests.
- Incident joins allow filtering runs by incident type or linked incident.

Source Phase 2 exit criterion:

- Incidents and promotion records retain links to source run events and artefacts.

Concrete acceptance:

- Incident join tables preserve run/event links.
- Promotion records include source run, source events in payload, target type, owner/review metadata, and artifact/evidence links.

---

## 25. Definition Of Done

Phase 2 is done when:

- Local workspace storage initializes and reopens reliably.
- Initial migration creates all required tables and indexes.
- Repository registration is implemented and tested.
- Snapshot ledger supports clean, dirty, stale, partial, mixed, and unknown states.
- Graph nodes and edges can be written transactionally.
- Graph query primitives work over fixture graphs.
- Graph slice results include snapshot consistency and truncation metadata.
- Harness metadata store persists active manifest hashes, permission profile, sandbox/runtime descriptors, verification gate versions, and dependency/analyser versions.
- Operational store persists run records, run events, harness conditions, policy decisions, budget/compaction events, monitor alerts, incidents, readiness reports, and promotion records.
- Run records are queryable by repo, workflow, status, incident type, and time.
- Incidents and promotion records preserve source run/event and artefact links.
- Artifact registry stores hashes and redaction status.
- Basic graph export/import works.
- Storage tests cover transactions, invalid writes, mixed snapshots, and export/import validation.
- Storage documentation explains the boundaries for Phase 3 indexing and Phase 4 MCP.

---

## 26. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Store API leaks raw SQL into feature code | Later phases become hard to migrate or test | Use typed repository interfaces and keep SQL inside storage modules |
| JSON columns hide query-critical data | Queries become slow or impossible | Index common fields: repo, snapshot, type, file, span, run, workflow, status, time |
| Graph store accepts facts without validation | Later verdicts trust malformed evidence | Validate Phase 1 models before all writes |
| Snapshot state is too vague | Stale evidence produces confident verdicts | Store snapshot IDs on graph facts and return consistency metadata from every graph slice |
| Run events are mutable | Operational review cannot reconstruct what happened | Enforce append-only event writes and correction events instead of updates |
| Large artefacts are stored inline | Database grows quickly and exports leak data | Store large payloads as artefacts with hashes and redaction status |
| Repository paths leak in exports | Privacy and portability issues | Use redacted export views and path hashes by default |
| Migration mistakes corrupt local evidence | Users lose audit data | Use migration checksums, backups before risky migrations, and transaction-based migration tests |
| Query APIs return unbounded full graphs | MCP clients or LLM context overload | Require limits, truncation metadata, and manifest/chunk exports |
| Operational and graph stores are disconnected | Evidence cannot be tied back to harness conditions | Preserve source run/event IDs in provenance and explicit fields |

---

## 27. Phase 2 Completion Report Template

When Phase 2 implementation is complete, report:

```text
Phase 2 completion report

Implemented:
- Workspace store:
- Repository registry:
- Snapshot ledger:
- Graph store:
- Graph queries:
- Harness metadata store:
- Operational store:
- Artifact registry:
- Export/import:
- Migrations:

Verification:
- Workspace tests:
- Registry tests:
- Snapshot tests:
- Graph store/query tests:
- Operational store tests:
- Export/import tests:
- Transaction tests:
- Local verify command:

Exit criteria:
- register_repo stores metadata:
- graph facts can be added and queried:
- dirty worktree snapshots represented:
- mixed-snapshot queries detectable:
- stored evidence tied to harness condition:
- run records queryable by repo/workflow/status/incident/time:
- incidents and promotions retain source links:

Known limitations:
-

Follow-up for Phase 3:
-
```

---

## 28. Minimal First Slice Within Phase 2

If Phase 2 needs to be split further, implement this first:

1. Workspace initialization.
2. Initial SQLite migration.
3. Repository registry.
4. Snapshot ledger.
5. Graph node and edge tables.
6. `add_node`, `add_edge`, `fetch_by_id`, `fetch_by_type`.
7. Dirty snapshot fixture.
8. Mixed-snapshot detection helper.
9. Run record and run event tables.
10. `create_run`, `append_run_event`, `get_run`.
11. Harness Condition Sheet table.
12. Basic graph export/import fixture.

This minimal slice unblocks Phase 3 indexing while preserving the core auditability guarantees needed by Phase 4A.
