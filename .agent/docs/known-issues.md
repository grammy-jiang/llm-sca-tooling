# Known Issues

## KI-001 — `graph_build` always returns `edges_added: 0`

**Symptom**: After a successful `graph_build` run, the result reports
`edges_added: 0` and `status: "failed"`, even though `nodes_added` is
non-zero (e.g. 31 000+ nodes for a large Python repo). The MCP tool returns:

```json
{"status": "failed", "nodes_added": 31148, "edges_added": 0}
```

**Affected tools**: `graph_build`, `get_relevant_files` (returns empty list),
`run_implementation_check` (all clauses return `unknown`).

**Root cause**: `graph_store.GraphStore.add_edges()` performs a strict
endpoint integrity check before writing each edge:

```python
# storage/graph_store.py:161-183
async def add_edges(self, edges: list[GraphEdge]) -> StoreWriteResult:
    async with self._session_factory() as session, session.begin():
        for edge in edges:
            src = await session.get(GraphNodeRow, edge.source_id)
            tgt = await session.get(GraphNodeRow, edge.target_id)
            if src is None or tgt is None:
                raise GraphIntegrityError(...)  # rolls back entire batch
```

When `_emit_import_edge` in `indexing/backends/python_ast.py` creates an
`imports` edge it computes the target node ID as:

```python
target_id = make_node_id(repo_ref.repo_id, "module", target_path)
```

where `target_path` is the *file path* of the imported module (e.g.
`src/research_pipeline/models/candidate.py`). However, the corresponding
module node is stored under `make_node_id(repo_id, "module", rel_path)`
where `rel_path` may differ — the node writer uses the scanner-local
relative path which can include or omit the `src/` prefix depending on
how files are enumerated.

When the first edge with a mismatched endpoint ID is attempted,
`GraphIntegrityError` propagates up through `_do_build()` into the outer
`try-except Exception` in `IndexingService.graph_build()`, which catches it,
logs the error, and records `result.finish("failed")` — leaving `edges_added`
at its initialised value of `0`.

**Impact**:
- `get_relevant_files` cannot return file evidence (graph queries find no edges).
- `run_implementation_check` returns all clauses as `unknown` because the
  clause verifier cannot locate implementing files via graph traversal.
- `run_readiness_audit`, `assess_harness_stage`, `classify_harness_drift`,
  `compute_readiness_score`, and `validate_harness_controls` are **not**
  affected — they use file-system checks, not graph edges.

**Workaround**: All six operational harness tools (`assess_harness_stage`,
`classify_harness_drift`, `compute_readiness_score`, `validate_harness_controls`,
`detect_run_anomalies`, `compare_run_traces`) work without graph edges.
For clause-level implementation checks, supplement the `run_implementation_check`
output with direct code inspection (grep/glob) until this issue is fixed.

**Fix path**:
Change `add_edges` from a strict integrity-check-and-raise pattern to a
*skip-and-count* pattern for unresolvable endpoints:

```python
# Proposed fix in storage/graph_store.py
if src is None or tgt is None:
    result.skipped += 1   # log but continue instead of raising
    continue
```

Alternatively, normalise the node ID generation so that the path used in
`_emit_import_edge` exactly matches the path used when the target module
node was written (require both to go through the same `rel_path_key`
function).

**Tracking**: See also the `status: "failed"` in `IndexingResult` returned
from `run_implementation_check` when the graph has 0 edges. Until this is
fixed, the `overall_verdict` will always be `"unknown"` for any repo.

**First observed**: 2026-05-11 during audit of `research-pipeline`
(session `9a8053db-fd73-4216-a6be-285d729af025`).
