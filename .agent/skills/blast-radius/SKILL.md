# blast-radius

Private Phase 15 skill for cross-file, cross-language blast-radius analysis.

Use before committing or reviewing a patch to bound the impact surface.

## Preconditions

- A candidate patch diff or a set of changed files/symbols.
- The repository is registered and indexed.

## Steps

1. Extract changed file paths and symbol names from the patch or diff.
2. Call `get_graph_slice` with `depth=2` to find all callers and callees.
3. Call `find_callers` for each changed public symbol to identify downstream consumers.
4. Call `trace_cross_language` if the change crosses a language or framework boundary.
5. Identify critical paths: test infrastructure, CLI entrypoints, exported APIs.
6. Summarise: direct impact (changed files), indirect impact (callers/callees), cross-language impact.
7. Flag if blast radius crosses a critical path or exceeds 20 files/symbols.

## Done

- Blast radius report lists direct, indirect, and cross-language impact.
- Critical path crossings are explicitly noted.
- Report is attached to the patch review evidence before `run_patch_review` is called.
