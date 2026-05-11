# Audit

Private Phase 18 readiness audit template.

Use `run_readiness_audit` and `compute_readiness_score` to evaluate a
repository's AI-readiness across five axes:
1. Harness controls (HC1–HC6) presence and drift classification.
2. CI workflow coverage (verify, governance, secrets scan).
3. Documentation completeness (AGENTS.md, plan.md, HCS templates).
4. Security controls (detect-secrets, Bandit, dep audit).
5. Graph and SARIF index freshness.

Report the total score (0–25), per-axis breakdown, and any MISSING or
RELAXED drift findings that block release.
