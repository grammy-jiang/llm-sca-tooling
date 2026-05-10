# Evaluate

Private Phase 10 evaluation template.

Use `run_eval_suite` with `suite="smoke"` or `suite="t1"` and
`null_mode=true` for the local baseline. Every reported benchmark result must
include a Harness Condition Sheet, FL-conditioned repair rate, RDS summary,
suite freshness, contamination canary result, and stored eval artefact manifest.

Do not call external benchmark services in Phase 10.
