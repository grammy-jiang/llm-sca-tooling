# Evaluate

Phase 10 evaluation skill (T1/T2/T3/T4 suites, RDS v0.2).

Use this skill when launching or inspecting the local evaluation harness.

## Runner selection

| Tier | Class | Use when |
|------|-------|----------|
| T1 (smoke) | `run_eval_suite` | quick null / sanity pass |
| T2 (regression) | `T2RegressionRunner` | compare two eval snapshots for metric regression |
| T3 (cross-language) | `T3CrossLanguageRunner` | multi-language fixture suites via `BenchmarkAdapter` |
| T4 (impl-spec) | `T4ImplSpecRunner` | full implementation-check benchmark suites |

## Workflow

1. Run `run_eval_suite` with `suite="smoke"` or `suite="t1"` and
   `null_mode=true` for a quick sanity pass.
2. For regression detection, instantiate `T2RegressionRunner(adapter, workspace)`
   and call `.run(baseline_run_id, candidate_run_id)`. Report any metric
   regressions (top-1 FL, repair rate, precision).
3. For T3/T4, pass a concrete `BenchmarkAdapter` (e.g. `LocalSmokeAdapter`)
   as the first constructor argument.
4. Poll the returned task and read `code-intelligence://eval/{run_id}`.
5. Report the Harness Condition Sheet, FL top-1/top-3/top-N metrics, the
   FL-conditioned repair rate, and all six **RDS v0.2 feature axes**:
   - `chain_depth` — mean reasoning chain depth from `compute_rds_features`
   - `cross_file_dataflow` — dataflow edges crossing file boundaries
   - `test_brittleness` — ratio of test-only edits to total edits
   - `memorisation_distance` — BLEU-based distance from training fixtures
   - `repair_rate` / `precision` — from `EvalRun` metrics
6. Report suite freshness, contamination canary verdict, and artefact manifest reference.
7. Network egress is denied by default; use `LocalSmokeAdapter` for offline runs.
