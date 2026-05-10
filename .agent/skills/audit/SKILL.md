# audit

Private Phase 18/19 skill for structured operational review of a run or release.

Use when reviewing a completed workflow run for compliance, trace completeness,
and harness condition adherence.

## Preconditions

- A stored run_id in the operational store.
- Harness condition sheet captured at run time.

## Steps

1. Read the run record via `code-intelligence://runs/{run_id}`.
2. Read the harness condition sheet via `code-intelligence://runs/{run_id}/harness-condition`.
3. Invoke `detect_run_anomalies` to surface policy violations, budget stops, and failed gates.
4. Invoke `classify_harness_drift` to check manifest and policy alignment.
5. Check `code-intelligence://operations/{repo}/ledger` for related policy decisions.
6. Invoke `run_operational_review` for the structured compliance report.
7. If anomalies are found: determine whether `record_incident` is warranted.

## Done

- `run_operational_review` returns `process-compliant` or a documented non-compliance.
- All anomalies are addressed (incident opened or waiver recorded).
- Harness drift is CLEAN or waived with evidence.
