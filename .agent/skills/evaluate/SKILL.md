# Evaluate

Private Phase 10 evaluation skill.

Use this skill when launching or inspecting the local evaluation harness.

Workflow:

1. Run `run_eval_suite` with `suite="smoke"` or `suite="t1"` and
   `null_mode=true`.
2. Poll the returned task and read `code-intelligence://eval/{run_id}`.
3. Report the Harness Condition Sheet, FL top-1/top-3/top-N metrics, the
   FL-conditioned repair rate, RDS summary, suite freshness, contamination
   canary verdict, and artefact manifest reference.
4. Treat T3/T4 as unavailable in Phase 10; do not perform network calls.
