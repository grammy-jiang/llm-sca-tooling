# Patch-Review Workflow

The `run_patch_review` MCP tool runs a four-axis review of a code patch and
returns a `PatchReviewReport` with per-axis `AxisFinding` records and an
overall risk classification.

## Axes

1. **Correctness** — logic regressions, off-by-one errors, unhandled edge
   cases, invariant violations, and missing null/error checks.
2. **Security** — injection points, credential handling, input validation gaps,
   OWASP Top 10 surface, and deviation from HC1–HC6 constraints.
3. **Performance** — algorithmic complexity changes, hot-path allocations,
   lock contention, and latency-sensitive path impacts.
4. **Compatibility** — breaking API or schema changes, dependency version
   conflicts, and cross-language interface drift.

## Evidence sources

The patch-review pipeline gathers evidence in this order:

1. **Graph slice** — retrieve `get_graph_slice` for each changed file to
   understand the call graph and upstream/downstream dependencies.
2. **SARIF delta** — compare pre/post SARIF alerts to surface new findings
   introduced by the patch.
3. **Interface contract** — call `get_interface_contract` for any
   changed public symbols; flag breaking changes.
4. **Sampling** — dispatch the four audit axes in parallel via MCP Sampling
   when a live backend is available, or fall back to the deterministic
   `FallbackSamplingClient` when offline.

## Hard rules

- A **block** recommendation from any single axis dominates the overall verdict
  regardless of other axes.
- Security findings from SARIF or HC1–HC6 violations always produce a **block**
  and cannot be downgraded.
- If SARIF delta or graph slice data is unavailable, record the limitation in
  `AxisFinding.uncertainty` and lower the confidence level accordingly.
- Graph slices must be fetched before the audit runs; do not skip this step
  even if the diff is small.
- The four sampling calls must run in parallel (via `ThreadPoolExecutor` or
  equivalent); sequential execution violates the multi-agent-info-theory design.

## Recommendation mapping

| Overall verdict | Recommendation |
|---|---|
| clean | merge-supporting |
| needs_review | review-required |
| blocked | block |
| unknown | review-required |

## Usage

```
run_patch_review(
  diff="<unified diff string or file path>",
  repos=["<repo_id>"],          # optional
  include_sarif_delta=true,     # default true
  run_id="<optional stable id>"
)
```

Always cite `report.report_id` and surface per-axis `AxisFinding.evidence`
and `AxisFinding.risk_signals` when justifying a block or review-required
outcome. Reference the graph slice node IDs that contributed to the verdict
so the caller can navigate to the relevant code.
