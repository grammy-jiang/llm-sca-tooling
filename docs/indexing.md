# Repository indexing MVP

Phase 3 adds deterministic repository indexing for local evidence capture. The
entrypoints are:

```python
from llm_sca_tooling.indexing import graph_build, graph_update

result = graph_build("/path/to/repo")
update = graph_update("/path/to/repo")
```

The CLI wrapper exposes the same operations:

```bash
evidence-sca graph-build /path/to/repo
evidence-sca graph-update /path/to/repo
```

Both commands create or reuse the Phase 2 workspace, register the repository,
capture git/snapshot metadata, scan files with deterministic ignore rules, run
the built-in Python AST backend, record build/test evidence, persist graph facts,
write graph manifests, and append operational run events.

## Deterministic scope

The MVP intentionally does not run tests, invoke linters, call LLMs, or execute
static-analysis tools. It only records repository-derived evidence:

- filesystem containment for directories, files, modules, and packages;
- Python AST symbols, imports, calls, and test relationships;
- package/test/CI configuration evidence;
- git metadata for clean, dirty, and non-git worktrees;
- optional ctags/tree-sitter capability diagnostics when those tools are not
  available.

`graph_update` uses git metadata to identify changed, staged, and untracked files
and re-indexes that subset when possible. Dirty worktrees receive deterministic
content-addressed snapshot identifiers so repeated runs over the same contents
produce the same snapshot id.

## Context helpers

`GraphSliceGenerator` returns bounded context for a file or symbol from the local
graph store:

```python
from llm_sca_tooling.indexing import GraphSliceGenerator

slice_generator = GraphSliceGenerator(workspace)
file_context = slice_generator.by_file(
    repo_id="repo:...",
    file_path="src/pkg/core.py",
)
```

Summary cache records are keyed by repository, snapshot, symbol, file path, and
file hash. Updates invalidate cached summaries for changed files without
generating new summaries.
