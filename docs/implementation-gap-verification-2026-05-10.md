# Implementation Gap Verification Report

Date: 2026-05-10

Specification reviewed: `docs/llm-sca-tooling-architecture.md`

Primary verdict: **partially fulfilled; not yet comprehensive**

The repository has broad implementation coverage for the architecture, but the
architecture document describes a production-grade, evidence-calibrated
LLM-assisted static-analysis system. The current implementation is closer to a
well-tested S3 scaffold with many workflow surfaces, conservative verdict
policies, and several null/stub/fallback adapters. The repo's own MCP
implementation check also reached this conclusion: `partially_compliant`,
`review-required`.

## What Happened

1. Read `docs/llm-sca-tooling-architecture.md` and extracted the feature set:
   F1 repository intelligence graph, F2 fault localisation, F3 repo-QA, F4
   implementation-check, F5 bug-resolve, F6 patch-review/risk, F7 SAST repair,
   F8 blast radius, F9 dynamic trace augmentation, F10 trajectory memory, and
   F11 operational harness.
2. Loaded the repository's MCP-provided implementation-check skill from
   `code-intelligence://skills/impl-check`.
3. Built the local evidence graph through the repository MCP server using
   `graph_build`.
4. Ran the repository MCP implementation checker against
   `docs/llm-sca-tooling-architecture.md`.
5. Ran MCP harness/readiness checks and maintainability oracles.
6. Ran local quality and targeted feature tests.
7. Compared the implemented code paths against the architecture's expected
   behaviour and evidence requirements.

## Verification Evidence

### MCP evidence

- `graph_build` completed and produced a local graph snapshot.
- Graph manifest after build:
  - 5,554 nodes
  - 10,377 edges
  - status: `partial`
  - snapshot caveat: dirty worktree
- `run_implementation_check` result:
  - report: `.llm-sca/artifacts/impl_check/report_2b2738cfa093b6226e2ac470.json`
  - report id: `impl-check-report:291bffa38bee0c4697ebde82`
  - run id: `impl-check:76f1c41c32f3ebf4`
  - overall verdict: `partially_compliant`
  - recommendation: `review-required`
  - satisfied clauses: 16
  - unknown clauses: 112
  - violated clauses: 0
  - security clauses: 3, all `unknown`
  - harness policy clauses: 24, all `unknown`
- `validate_harness_controls` passed.
- `assess_harness_stage` reported S3 with clean harness drift and readiness
  score 23, but still listed production evaluation work as next-stage controls.

### Local command evidence

Passing checks:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync ruff check src tests
UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync mypy src
UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync lint-imports
UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync pytest tests/unit/ -x -q
UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync pytest \
  tests/indexing tests/mcp_server tests/plugins \
  tests/workflows/impl_check tests/workflows/bug_resolve \
  tests/patch_review tests/sast_repair tests/blast_radius \
  tests/traces tests/memory tests/evaluation tests/release tests/harness -q
```

`make verify` did not complete. It stopped at `black --check`:

```text
would reformat src/llm_sca_tooling/cli/setup_cmd.py
would reformat tests/unit/test_cli.py
```

The worktree was already dirty during verification. At report time, dirty paths
included `.codex/config.toml`, `src/llm_sca_tooling/cli/setup_cmd.py`,
`src/llm_sca_tooling/mcp_server/dev_server.py`, `tests/unit/test_cli.py`,
`tests/unit/test_setup.py`, `.agent/mcp-smoke/`, and
`src/llm_sca_tooling/mcp_server/stdio_compat.py`. This report does not attempt
to attribute those changes.

## How We Know The Current Implementation Is Partial

The architecture requires each user-facing workflow to return structured,
auditable verdicts with evidence, calibrated confidence, run records,
uncertainty, and recommended actions. It also says mixed snapshots, missing tool
support, or uncalibrated classifier families must force `unknown` or human
review.

The implementation follows that conservative shape, but many places still lack
the hard evidence needed to convert `unknown` into `satisfied`:

- The MCP tool registry exposes the expected workflow surfaces in
  `src/llm_sca_tooling/mcp_server/tools/core.py`.
- MCP resources expose graph, schema, SARIF, eval, memory, governance, and
  readiness surfaces in `src/llm_sca_tooling/mcp_server/resources/core.py`.
- The implementation-check workflow has the intended seven-stage DAG in
  `src/llm_sca_tooling/workflows/impl_check/report.py`.
- However, implementation-check clause extraction is regex-based and targets
  mostly backticked identifiers in
  `src/llm_sca_tooling/workflows/impl_check/clause_extractor.py`.
- Implementation-check contract generators are null/stub generators in
  `src/llm_sca_tooling/workflows/impl_check/contract_generator.py`.
- Bug-resolve defaults to pass-through/null behaviour in parts of
  `src/llm_sca_tooling/workflows/bug_resolve/state_machine.py`.
- Patch-risk classification is deterministic-first, with a trained classifier
  only accepted after calibration gates in
  `src/llm_sca_tooling/patch_review/risk_classifier.py`.
- Several language backends are availability shims or builtin fallbacks rather
  than full external analyser integrations.

The strongest single evidence item is the repo's own MCP implementation-check
report: 16 satisfied, 112 unknown, 0 violated. That means the checker found no
hard contradiction, but could not prove comprehensive implementation.

## Missing Or Incomplete Areas

| Area | Expected by architecture | Current evidence | Gap | Fix direction |
|---|---|---|---|---|
| F1 repository graph | Typed graph with files, symbols, interfaces, SARIF, build/test evidence, docs, traces, patches, verdicts, and rich edges such as `dataflow`, `warned_by`, `implements`, `fixed_by` | Graph build works and produced thousands of nodes/edges, but current graph was `partial` and mostly contained `contains`, `imports`, `calls`, `documents`, `tests`, and `exposes` edges | Foundational graph exists, but edge coverage and evidence-node coverage are not complete enough for the full architecture | Extend graph population for SARIF links, generated contracts/tests, traces, patches, verdicts, data-flow, ownership/nullness, interface consumers, and fixed-by relationships |
| F1 language backends | tree-sitter, universal-ctags, libclang/clangd, pyan3, ts-morph/madge, Java where enabled | Python/C++/TS surfaces exist, but several adapters are builtin parsers, diagnostic-only paths, or stubs | Analyzer integration is incomplete compared with the architecture's "existing tools as backends" design | Implement real subprocess/API calls for ctags, tree-sitter grammars, ts-morph/madge, libclang, and Java JDT; keep fallback mode explicit and lower-confidence |
| F2 fault localisation | Semantic retrieval, graph expansion, optional SBFL/Ochiai, blame/history, ranked file/symbol candidates with rejected alternatives | Localisation-related tools and tests exist, but this verification did not find production benchmark evidence for FL accuracy | Workflow surface exists, acceptance evidence is incomplete | Add T1/T2 FL benchmark runs, store top-1/top-3 metrics, and require graph/SBFL/blame feature attribution in outputs |
| F3 repo-QA | Evidence-cited file-location, symbol-location, behaviour-tracing, and contract-check answers with `unknown` when insufficient | QA modules and MCP tools exist; broad MCP QA query returned insufficient evidence and requested a more specific token | Repo-QA is not proven comprehensive for architecture-level behaviour tracing | Add benchmark-backed file-location and behaviour-trace gates; require cited graph paths for audit-grade answers |
| F4 implementation-check | Clause extraction, intent graph, executable contract generation, graph grounding, static/dynamic verdicts, calibrated aggregation | Seven-stage DAG exists, but clause extraction and contract generation are mostly heuristic/null; MCP report left 112 clauses unknown | This is the largest direct gap against the user's requested verification | Replace null contracts with real pytest/Semgrep/CodeQL/schema/test generation; improve clause extraction; bind clauses to graph/doc nodes; add dynamic hooks and calibration evidence |
| F5 bug-resolve | Locate root cause, generate repair candidates, create pre/postconditions, generate reproduction tests, run deterministic gates, run patch-risk, run blast-radius | State machine exists, but null mode has placeholder pre/postconditions, placeholder reproduction tests, pass-through gates, and static medium risk | Current default path is a scaffold, not a production autonomous bug resolver | Wire real localisation, patch generation, reproduction-test generation, SARIF/build/test/interface gates, and patch-risk output into default non-null workflows |
| F6 patch-review/risk | Multi-axis review with calibrated risk classifier and hard overrides for SARIF/tests/interfaces/PoC+ | Patch review pipeline exists and deterministic risk policy is conservative; trained classifier is placeholder/advisory unless calibration passes | No evidence of calibrated classifier meeting architecture gates | Build calibration dataset, train/evaluate classifier, store macro-F1/ECE, and only allow merge-supporting `safe` when calibration family passes |
| F7 SAST repair | Bind SARIF alert, explain predicate, retrieve clean examples, generate patch, rerun analyser, compare SARIF delta, run tests | SAST repair loop exists with alert binding, classification, examples, sandboxing, analyser rerun hook, SARIF delta, build/test hook, and remaining risk notes | Production completeness depends on real analyser runners, corpus adapters, and graph data-flow completeness | Add real Semgrep/CodeQL/Bandit runners, predicate-example corpus, and end-to-end alert repair fixtures with before/after SARIF evidence |
| F8 blast radius | Cross-language and cross-repo traversal over calls, tests, interfaces, generated stubs, downstream repos, SARIF reachability, docs/spec impact | Cross-language traversal exists; `include_cross_repo` currently emits a diagnostic requiring interface plugins | Cross-repo impact is not yet a complete downstream dependency system | Add repo registry for downstream consumers, interface-contract dependency records, generated-stub handling, and cross-repo fixtures |
| F9 dynamic trace augmentation | Python, JS/TS, and C/C++ trace adapters with scope filters, redaction, raw artefacts, compressed trace events, divergence/state diffs | Trace modules and integration hooks exist, and tests passed | This verification did not prove language adapter maturity beyond test fixtures | Add trusted reproduction fixtures per language and prove trace capture, redaction, compression, and workflow integration under timeout/failure conditions |
| F10 trajectory memory | Coarse-to-fine retrieval, utility-aware eviction, hindsight relabelling, misalignment guard, audit trail | Memory tools/resources exist | Needs quality evidence that memories improve workflows without overriding current hard evidence | Add memory utility metrics, rejected-memory tests, retention/eviction tests, and benchmark comparisons with memory on/off |
| F11 operational harness | Run records, harness condition sheets, policy gates, budget monitors, incidents, readiness scoring, prompt/manifest regression, release gates | Harness controls passed; stage S3 clean; maintainability oracles passed | Release gates are not complete; next-stage controls still include T1-T4, ECE across model runs, adversarial/ablation checks | Run and store full evaluation ladder under `code-intelligence://eval/{run_id}`; make release readiness depend on those stored artefacts |

## Recommended Fix Plan

### Phase 0: Stabilise The Worktree

Expected outcome: `make verify` can complete from a clean baseline.

Tasks:

1. Review the current dirty files and decide which changes are intentional.
2. Run formatting on intentional changes:

   ```bash
   UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync black --workers 1 \
     src/llm_sca_tooling/cli/setup_cmd.py tests/unit/test_cli.py
   ```

3. Re-run:

   ```bash
   make verify
   ```

Acceptance:

- `git status --short` contains only intended files.
- `make verify` passes or any external-tool limitation is explicitly recorded.

### Phase 1: Make Implementation-Check Audit-Grade

Expected outcome: `run_implementation_check` can prove or disprove a useful
majority of architecture clauses instead of returning mostly `unknown`.

Tasks:

1. Replace regex-only clause extraction with a structured Markdown/spec parser
   that handles tables, feature sections, bullet lists, and source spans.
2. Preserve rejected interpretations and split compound clauses into atomic
   clauses.
3. Generate executable contracts where possible:
   - pytest tests for behavioural clauses
   - Semgrep/CodeQL/Bandit predicates for security/static clauses
   - schema/OpenAPI/IDL checks for interface clauses
   - dynamic trace requirements for runtime-only clauses
4. Require generated contracts to compile/lint before they can provide hard
   evidence.
5. Bind each clause to graph nodes, document nodes, interface records, SARIF
   alerts, tests, or explicit missing-grounding evidence.
6. Store clause verdict matrices and calibration metadata as graph/eval
   evidence.

Acceptance:

- Running `run_implementation_check` on
  `docs/llm-sca-tooling-architecture.md` produces materially fewer unknowns.
- Security clauses are not satisfied by repo-QA alone.
- Each satisfied clause cites hard evidence.
- Each unknown clause has a specific missing-evidence reason.

### Phase 2: Complete The Repository Graph Backends

Expected outcome: graph evidence is strong enough to support localisation,
repo-QA, implementation-check, patch review, SAST repair, and blast radius.

Tasks:

1. Implement real ctags invocation and merge parsed ctags facts into graph
   facts.
2. Implement real tree-sitter parsing for installed grammars, not just
   availability diagnostics.
3. Replace TypeScript regex fallback with actual ts-morph integration when
   Node dependencies are available; use madge for import graph evidence.
4. Wire libclang and clangd outputs where available, while keeping fallback
   evidence marked lower-confidence.
5. Implement Java backend behaviour or mark Java as unsupported in architecture
   and docs until it exists.
6. Add graph edges for SARIF warning links, data-flow where supported, tests,
   interface producers/consumers, documents, generated artefacts, patches, and
   verdicts.

Acceptance:

- Graph manifest includes required edge/node families for representative
  fixtures.
- Backends report installed/unavailable/fallback modes explicitly.
- Dirty or partial snapshots continue to force conservative verdicts.

### Phase 3: Turn Bug-Resolve From Scaffold Into Real Workflow

Expected outcome: bug-resolve can locate, patch, verify, risk-review, and
explain fixes on controlled fixtures without relying on null gates.

Tasks:

1. Make non-null mode the primary test path.
2. Generate issue-anchored reproduction tests and require them to fail on the
   buggy version for the expected reason.
3. Replace placeholder pre/postconditions with generated or inferred contracts
   tied to changed functions.
4. Wire build/test/SARIF/interface gates into the default workflow.
5. Use F6 patch-risk results instead of static `medium` risk placeholders.
6. Record blast-radius and operational-review evidence for each selected patch.

Acceptance:

- Fixture bugs produce a root-cause explanation, patch, reproduction evidence,
  gate results, patch-risk result, and blast-radius map.
- Null-mode tests remain only for isolated unit tests.

### Phase 4: Calibrate Patch Risk And Repo-QA

Expected outcome: merge-supporting verdicts rely on measured calibration, not
only deterministic policy or soft model evidence.

Tasks:

1. Build a calibration set by language/rule family.
2. Train or plug in a patch-risk classifier.
3. Store macro-F1 and ECE for each calibration family.
4. Add repo-QA benchmark runs for file-location and behaviour-tracing classes.
5. Enforce architecture thresholds:
   - patch-risk classifier macro-F1 >= 0.75
   - patch-risk ECE <= 0.10
   - repo-QA behaviour-tracing gate >= 70% before audit-grade use

Acceptance:

- `safe` patch-risk labels are merge-supporting only for calibrated families.
- Behaviour-tracing answers without graph evidence remain supporting evidence
  or `unknown`.

### Phase 5: Complete Release/Evaluation Evidence

Expected outcome: features can be called production-ready only when current
stored eval runs prove their sub-metrics.

Tasks:

1. Run T1 smoke, T2 regression, T3 cross-language, and T4 implementation/spec
   evaluation ladders.
2. Store results under `code-intelligence://eval/{run_id}`.
3. Log RDS v0.2 features.
4. Add adversarial and ablation checks.
5. Record calibration across at least three model runs where model evidence is
   used.
6. Promote only reviewed lessons/rules/memories with source, owner, review due
   date, acceptance check, and rollback path.

Acceptance:

- Release readiness is derived from stored eval artefacts, not ad hoc test
  success.
- Harness gates can block production readiness when trace completeness,
  policy compliance, budget reliability, drift, or incidents fail.

## Expected End State

The implementation should be considered comprehensive only when all of the
following are true:

1. `make verify` passes on a clean worktree.
2. MCP `graph_build` returns a fresh graph for a clean snapshot.
3. Required graph node and edge families from the architecture are populated
   for representative Python, C/C++, JS/TS, interface, SARIF, test, trace, and
   document fixtures.
4. `run_implementation_check` over the architecture doc returns a clause matrix
   where satisfied/violated verdicts cite hard evidence and remaining unknowns
   have explicit missing-evidence reasons.
5. Bug-resolve fixtures run in non-null mode and produce patch, reproduction,
   gates, risk, blast-radius, and operational evidence.
6. Patch-risk uses calibrated classifier evidence where it claims merge support.
7. SAST repair proves before/after SARIF deltas with real analyser runners.
8. Repo-QA and localisation have stored benchmark metrics.
9. Dynamic trace adapters are validated on trusted reproductions with redaction
   and compression.
10. Memory improves or safely rejects prior trajectories under measured
    utility tests.
11. Full T1-T4 evaluation and calibration evidence is stored and linked from
    readiness resources.

## Re-Run Checklist

After implementing fixes, use this sequence:

```bash
make verify
```

Then rebuild and inspect MCP evidence:

```bash
evidence-sca graph-build /home/grammy-jiang/projects/evidence-sca
```

Then run the MCP implementation checker again against:

```text
docs/llm-sca-tooling-architecture.md
```

Expected improvement:

- `overall_verdict` moves from `partially_compliant` toward `compliant`.
- Unknown clause count drops substantially from 112.
- Security and harness policy clauses are resolved by hard evidence or explicit
  missing-evidence findings.
- Graph status is `fresh` on a clean snapshot.
- T1-T4 eval resources exist for production-readiness claims.
