# evaluate

Arguments: `suite`, optional `target`, optional `null_mode`.

1. Read current Harness Condition Sheet metadata from the server.
2. Launch `run_eval_suite` for the requested suite.
3. Poll task state until completion when the tool returns a task handle.
4. Read `code-intelligence://eval/{run_id}`.
5. Report resolve-rate only with FL-conditioned repair rate, RDS v0.2 features, suite freshness, contamination canary, manifest regression verdict, and operational-quality metrics.
6. For external-quality claims, use `swe-bench-live` as the headline suite.
7. If the canary is `suspect` or `contaminated`, flag it before any quality claim.
8. If process compliance is below 90%, include an operational warning.
9. Do not present LLM-as-judge output as a deterministic gate.
10. Conclude with the Harness Condition Sheet reference.
