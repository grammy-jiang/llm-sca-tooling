# Evaluation Guide

Evaluation results should be reproducible and traceable:

- T1 and T2 measure baseline graph and workflow behavior.
- T3 measures integration, contamination, and replay-sensitive quality.
- T4 measures operational and release readiness.
- Calibration, adversarial refresh, operational gates, memory ship gates, and
  manifest regressions feed the release gate.

Use `uv run llm-sca-tooling release-gate --suite all` for the deterministic
aggregation smoke path. Attach the HarnessConditionSheet, eval run identifiers,
and verification command outputs to PR evidence.

## Limitations

The evaluation guide describes local deterministic gates. It does not certify
model quality for repositories outside the sampled corpus without additional
calibration evidence.
