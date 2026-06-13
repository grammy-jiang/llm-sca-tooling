# Session Plan: Real C/C++ indexing backend (libclang / clang.cindex)

session_id: cpp-real-backend-20260613
started: 2026-06-13
mode: scoped-execute
redaction_status: no_red_class_data_observed
branch: agent/cpp-real-backend

## Goal

Replace the regex-only C/C++ "fallback" with a real libclang-driven backend
(`clang.cindex`) emitting parser-grade graph facts (symbols, includes,
cross-file call edges), keeping the regex backend as graceful degradation.

## Key unblock (verified 2026-06-13)

The **`libclang` PyPI wheel (18.1.1) bundles a loadable native lib** —
`clang.cindex.Index.create()` works with no apt / system libclang. So C/C++ is
**buildable AND fully testable here and in CI via a pip/uv dependency**, NOT
the heavier CI-image path originally feared. Smoke test confirmed: symbols
(header decl + cpp def), and `cursor.referenced` resolves the cross-file call
`Calc::compute -> helper`. clang.cindex is **in-process** — no vendored runner
needed (simpler than the TS/Node backend).

## Architecture (same additive, confidence-ranked model as TS)

- Real backend emits `DerivationType.parser` full confidence -> wins
  `FactReconciler`; regex backend kept as fallback when libclang absent.
- Honesty: rename regex `cpp.libclang` -> `cpp.heuristic`, downgrade to
  heuristic/0.6 (it currently emits parser-grade dishonestly, like TS did).

## Phases

### Phase 1 — Real clang backend
1. `backends/cpp/clang_backend.py` — `ClangCppBackend`:
   - availability: `import clang.cindex` + `Index.create()` succeeds;
   - per file: `index.parse(path, args)` where args come from
     `compile_commands.json` if present, else defaults (`-std=c++17`,
     `-x c++`); walk AST for FUNCTION_DECL / CXX_METHOD / CLASS_DECL /
     STRUCT_DECL (definitions preferred), INCLUSION_DIRECTIVE, CALL_EXPR
     (`cursor.referenced` -> callee decl file+name);
   - map to GraphNode/GraphEdge at parser confidence;
   - delegate to regex `CppBackend` when libclang unavailable / parse fails.
2. Rename + downgrade regex `CppBackend` (cpp.libclang -> cpp.heuristic).
3. Wire into `service.py` both build paths.
4. `pyproject`: optional extra `cpp = ["libclang>=18.1.1"]`; mypy override
   for `clang.*` (no stubs).
5. Tests `tests/indexing/backends/test_clang_cpp_backend.py`: real .cpp/.h
   fixtures; assert methods + cross-file call edges; fallback path.
6. CI: install the `cpp` extra (`uv sync --extra cpp` or add to test step).

## Risks

- Cross-TU resolution needs include paths/flags; honour
  `compile_commands.json` when present, degrade to self-contained parsing
  otherwise (still resolves intra-TU + included headers).
- libclang wheel size + parse time in CI (acceptable; in-process).
- Node-absent / libclang-absent must both degrade to regex (tested).

## Decisions log

- 2026-06-13: User approved (a) release v0.14.0 then C++. libclang-pip unblock
  found -> C++ now same weight as TS, fully testable, no CI-image surgery.
