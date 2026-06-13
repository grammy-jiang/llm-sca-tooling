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
##[38;2;187;187;187m [39mRelease[38;2;187;187;187m [39mv0[38;2;102;102;102m.15[39m[38;2;102;102;102m.0[39m[38;2;187;187;187m [39m([38;2;102;102;102m2026[39m[38;2;102;102;102m-[39m[38;2;102;102;102m06[39m[38;2;102;102;102m-[39m[38;2;102;102;102m13[39m)

[38;2;102;102;102m-[39m[38;2;187;187;187m [39mPR[38;2;187;187;187m [39m#[38;2;102;102;102m17[39m[38;2;187;187;187m [39mmerged[38;2;187;187;187m [39m([38;2;102;102;102m16[39mac71e);[38;2;187;187;187m [39m[38;2;170;34;255;01mrelease[39;00m[38;2;187;187;187m [39mcommit[38;2;187;187;187m [39mace764c;[38;2;187;187;187m [39mtag[38;2;187;187;187m [39mv0[38;2;102;102;102m.15[39m[38;2;102;102;102m.0[39m[38;2;187;187;187m [39mpushed.
[38;2;102;102;102m-[39m[38;2;187;187;187m [39mReal[38;2;187;187;187m [39mlibclang[38;2;187;187;187m [39mC[38;2;102;102;102m/[39mC[38;2;102;102;102m+[39m[38;2;102;102;102m+[39m[38;2;187;187;187m [39mbackend[38;2;187;187;187m [39mshipped[38;2;187;187;187m [39m[38;2;102;102;102m+[39m[38;2;187;187;187m [39mran[38;2;187;187;187m [39mlive[38;2;187;187;187m [39min[38;2;187;187;187m [39mCI[38;2;187;187;187m [39m(uv[38;2;187;187;187m [39msync[38;2;187;187;187m [39m[38;2;102;102;102m-[39m[38;2;102;102;102m-[39mextra[38;2;187;187;187m [39mcpp).
[38;2;102;102;102m-[39m[38;2;187;187;187m [39m[38;2;160;160;0mGates:[39m[38;2;187;187;187m [39mno[38;2;187;187;187m [39mincidents;[38;2;187;187;187m [39mreadiness[38;2;187;187;187m [39mhXISo[38;2;102;102;102m-[39mYAHxHhF65hZ1sgePNw[38;2;187;187;187m [39m(S3[38;2;102;102;102m/[39m[38;2;102;102;102m22[39m);[38;2;187;187;187m [39mmake[38;2;187;187;187m [39mverify
[38;2;187;187;187m  [39mexit[38;2;187;187;187m [39m[38;2;102;102;102m0[39m;[38;2;187;187;187m [39mHCS[38;2;187;187;187m [39mhcs[38;2;102;102;102m-[39m[38;2;170;34;255;01mrelease[39;00m[38;2;102;102;102m-[39mv0[38;2;102;102;102m.15[39m[38;2;102;102;102m.0[39m;[38;2;187;187;187m [39mHC3[38;2;187;187;187m [39m[38;2;102;102;102m=[39m[38;2;187;187;187m [39m[38;2;187;68;68m"[39m[38;2;187;68;68mmerge and release[39m[38;2;187;68;68m"[39m.
[38;2;102;102;102m-[39m[38;2;187;187;187m [39mCI[38;2;187;187;187m [39mpublish[38;2;187;187;187m [39m[38;2;102;102;102m+[39m[38;2;187;187;187m [39mverify[38;2;187;187;187m [39mgreen;[38;2;187;187;187m [39mpipx[38;2;187;187;187m [39m[38;2;102;102;102m0.14[39m[38;2;102;102;102m.0[39m[38;2;187;187;187m [39m[38;2;102;102;102m-[39m[38;2;102;102;102m>[39m[38;2;187;187;187m [39m[38;2;102;102;102m0.15[39m[38;2;102;102;102m.0[39m;[38;2;187;187;187m [39mconfig[38;2;187;187;187m [39mvalidate[38;2;187;187;187m [39mok.
[38;2;102;102;102m-[39m[38;2;187;187;187m [39mLANGUAGE[38;2;102;102;102m-[39mBACKEND[38;2;187;187;187m [39mFIDELITY[38;2;187;187;187m [39mWORK[38;2;187;187;187m [39m[38;2;160;160;0mCOMPLETE:[39m[38;2;187;187;187m [39mTS[38;2;187;187;187m [39m(v0[38;2;102;102;102m.14[39m[38;2;102;102;102m.0[39m)[38;2;187;187;187m [39m[38;2;102;102;102m+[39m[38;2;187;187;187m [39mC[38;2;102;102;102m/[39mC[38;2;102;102;102m+[39m[38;2;102;102;102m+[39m[38;2;187;187;187m [39m(v0[38;2;102;102;102m.15[39m[38;2;102;102;102m.0[39m)[38;2;187;187;187m [39mboth
[38;2;187;187;187m  [39m[38;2;0;187;0;01mreal[39;00m[38;2;187;187;187m [39mparser[38;2;102;102;102m-[39mgrade;[38;2;187;187;187m [39mregex[38;2;187;187;187m [39mkept[38;2;187;187;187m [39mas[38;2;187;187;187m [39mhonest[38;2;187;187;187m [39mfallbacks.[38;2;187;187;187m [39mOnly[38;2;187;187;187m [39mremaining[38;2;187;187;187m [39mbackend
[38;2;187;187;187m  [39m[38;2;160;160;0mfallback:[39m[38;2;187;187;187m [39mjava.jdt[38;2;187;187;187m [39m(gated[38;2;187;187;187m [39moff,[38;2;187;187;187m [39msmaller[38;2;187;187;187m [39mfollow[38;2;102;102;102m-[39mup).
