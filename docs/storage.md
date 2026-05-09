# Phase 2 local storage

The storage package persists Phase 1 schema objects in a local SQLite workspace.
The default repo-local layout is:

```text
.llm-sca/
  workspace.db
  artifacts/
  exports/
  locks/
```

Storage is persistence-only. It does not scan repositories, build graph facts,
run static analysis, expose MCP routes, call LLMs, execute workflows, or retrieve
memory. Later phases should use typed store APIs instead of raw SQL.

Implemented boundaries:

- `WorkspaceStore` initializes SQLite, applies migrations, exposes component
  stores, and provides transaction helpers.
- `RepositoryRegistry` records local repositories and exposes redacted public
  metadata without absolute paths.
- `SnapshotStore` records clean, dirty, stale, partial, mixed, and unknown
  snapshots and detects mixed query results.
- `GraphStore` persists `GraphNode` and `GraphEdge` payloads with indexed lookup
  columns and graph slice metadata.
- `ArtifactStore` records artifact hashes, sizes, media types, and redaction
  status without requiring large payloads inline.
- `HarnessMetadataStore` records active and historical harness metadata plus
  supply-chain provenance.
- `OperationalStore` persists run records, append-only run events, harness
  conditions, generic operational records, incidents, promotions, and readiness
  reports.
- `ImportExportService` provides basic graph and run export bundles with schema
  version and payload-hash checks.

Graph slices include snapshot IDs, snapshot consistency, truncation state, and
the original Phase 1 node/edge payloads so downstream code can preserve
provenance and confidence. Public exports default to redacted metadata and path
hashes.
