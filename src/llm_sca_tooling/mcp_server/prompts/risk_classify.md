# Risk Classify

Private patch risk classifier template.

Use `classify_patch_risk` to derive a deterministic risk class and,
when a trained calibration family is available, a calibrated probability.

Workflow:
1. Parse the diff for files changed, symbols touched, and SARIF delta.
2. Apply the deterministic policy table (HC1–HC6, permission mode, blast radius).
3. Retrieve the calibrated probability from the calibration family if available.
4. Produce a `PatchRiskResult` with: risk_class, probability, policy_flags,
   and evidence_refs.
5. Flag any HIGH or CRITICAL risk class findings that require human approval.

Never approve a HIGH/CRITICAL risk patch without explicit human sign-off.
