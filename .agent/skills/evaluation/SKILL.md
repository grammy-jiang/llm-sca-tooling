# evaluation

Use when running a benchmark, regression suite, or readiness check.

## Preconditions

- Record runtime, model, manifest revisions, toolset hash, and permission mode.
- Freeze inputs and fixture versions.

## Steps

1. Create a Harness Condition Sheet.
2. Run the evaluation command.
3. Store raw outputs or stable summaries.
4. Record pass/fail, flaky tests, skipped gates, and residual risk.

## Done

- Results can be compared to a prior run under matching harness conditions.
- Any readiness regression has an owner and review date.
