# risk-classify

Use `risk-classify(diff="<unified diff>", repo?, agreement_score?)`.

1. Call `classify_patch_risk(diff)`.
2. Report risk class, calibrated probability, and ECE bucket.
3. List active overrides.
4. State the calibration family and flag `unknown` calibration explicitly.
5. Summarise AST diff, SARIF delta, graph context, tests, and vulnerability prior.
6. Include `InvestigateResult.agreement_score` as additional context (Phase 13).
7. Flag `correct-but-overfit_risk` when certificate conclusion is `unsupported` despite passing tests.
8. Give a recommendation based on classifier output and deterministic overrides.

Do not present classifier output as a standalone merge decision.
