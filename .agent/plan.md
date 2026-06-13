# Session Plan: Real TypeScript/JavaScript indexing backend (ts-morph)

session_id: ts-real-backend-20260613
started: 2026-06-13
mode: scoped-execute
redaction_status: no_red_class_data_observed
branch: agent/ts-real-backend

## Goal

Replace the regex-only TS/JS "fallback" with a real ts-morph-driven backend
that emits parser-grade graph facts, while keeping the regex backend as the
graceful-degradation path when Node/ts-morph is unavailable. C/C++ (libclang)
is deferred to a follow-up round (libclang absent from host + default CI).

## User decisions (2026-06-13)

- **C++ scope**: TS first; C/C++ real backend deferred to next round.
- **ts-morph delivery**: vendored Node runner script + pinned `package.json`
  inside the backend; CI runs `npm install`; users get a documented prereq.

## Architecture facts (verified)

- Backends implement `IndexBackend` protocol (`backends/base.py`):
  `backend_id`, `backend_version`, `supported_languages`,
  `detect_capabilities`, `index_files(ctx, files) -> BackendResult{nodes,
  edges, diagnostics}`.
- `FactReconciler.reconcile([results])` picks the **highest
  `provenance.confidence`** node per fact key (`fact_reconciler.py:54`).
  Regex fallback emits `DerivationType.heuristic` ~0.7. A real backend at
  `DerivationType.parser` + higher confidence wins reconciliation
  automatically — additive, no rip-and-replace.
- `service.py` appends each backend's `BackendResult` to `backend_results`
  (full build + incremental paths). TS already wired (fallback).
- Host: node v22 + npm 10 present (TS buildable + testable here).

## Phases

### Phase 0 — Honesty cleanup (no toolchain)
- Fix the hardcoded "ts-morph Node runner unavailable; using Python fallback"
  warning (`ts_backend.py:103`) — currently always emitted even though no Node
  attempt is made. Make availability reflect reality.

### Phase 1 — Real ts-morph backend
1. `backends/typescript/runner/` — vendored Node runner (`index.mjs` +
   pinned `package.json` with ts-morph) that reads a file list, parses with
   ts-morph, and emits JSON facts (modules, classes, functions, interfaces,
   imports, calls) with accurate spans and resolved cross-file call targets.
2. `backends/typescript/ts_morph_backend.py` — adapter:
   - availability: `node` on PATH + runner deps installed;
   - `index_files`: spawn the runner (asyncio subprocess), parse JSON,
     map to `GraphNode`/`GraphEdge` at `DerivationType.parser`, confidence
     higher than the heuristic path;
   - **delegate to the existing regex `TypeScriptBackend` when unavailable.**
3. Wire into `service.py` both build paths (prefer ts-morph; reconciler ranks).
4. Tests `tests/indexing/backends/test_ts_morph_backend.py`: real `.ts`/`.tsx`
   /`.js` fixtures; assert parser-grade facts the regex misses; availability
   -skip path covered.
5. CI: install Node + `npm install` in the runner dir before tests.

## Commands

- `node backends/.../runner/index.mjs <files>` (manual smoke)
- `uv run pytest tests/indexing/backends/test_ts_morph_backend.py`
- `make verify`

## Expected outputs

- `ts_morph_backend.py` + vendored runner + `package.json`/lockfile
- service wiring (both paths)
- new tests; CI Node step
- `backend_versions["typescript"]` reports a real ts-morph version when active

## Risks

- ts-morph fact -> graph-schema mapping fidelity is the hard 60% (not the
  subprocess). Map conservatively; reconciler dedupes vs ctags/tree-sitter.
- CI gains a Node install + npm step (time + a new failure surface).
- Node absent at runtime must degrade cleanly to the regex backend (tested).
- `.gitignore` managed section — do not hand-edit; vendored node_modules must
  not be committed (commit lockfile, npm install in CI).

## Decisions log

- 2026-06-13: TS-first, vendored runner per user. C++ deferred. Real backend is
  additive (confidence-ranked reconciliation), regex path kept as fallback.
