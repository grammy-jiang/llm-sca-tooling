Readiness audit prompt.

Use `run_readiness_audit` to produce a `ReadinessAuditReport` for the requested
repository. The report must include AI-readiness score, harness stage, drift
findings, missing gates, weak documentation/specification links, unprotected
risky paths, absent scanners, recommended readiness tasks, and a Harness
Condition Sheet reference.

Readiness thresholds by autonomy level:

- S0: greenfield bootstrap only.
- S1: assisted local tasks with narrow scope.
- S2: review-gated repository workflows.
- S3: production workflow claims with release gates.

Do not claim autonomous readiness when security, verification, or governance
gates are missing.
