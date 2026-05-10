Operational review prompt.

Use `run_operational_review` to produce an `OperationalReviewReport` for the
requested run. The report must include a Harness Condition Sheet reference,
process-compliance verdict, trace completeness, denied and approved actions,
budget behaviour, compaction loss, verification adequacy, maintainability
oracle results, and lessons eligible for promotion.

Valid process-compliance verdicts are:

- `process-compliant`
- `process-noncompliant`
- `trace-incomplete`
- `budget-exhausted`
- `needs-readiness-work`

Do not treat missing evidence as passing. Preserve `unknown` or a failing
verdict when trace, policy, budget, or verification evidence is absent.
