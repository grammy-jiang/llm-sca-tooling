# SKILL: evaluation

Run a benchmark or regression suite and record a Harness Condition Sheet.

---

## Preconditions

- The benchmark or regression suite is defined and reachable.
- A Harness Condition Sheet template is available at
  `.agent/templates/harness-condition-sheet.md`.
- `make verify` passes on the current branch before starting.
- The evaluation fixture set (if held-out) is available and hash-verified.

---

## Steps

1. **Copy the HCS template**: `cp .agent/templates/harness-condition-sheet.md
   .agent/eval/hcs-<run_id>.md`.
2. **Fill in Identification, Runtime And Model, and Manifest State** in the HCS
   before running any benchmarks.
3. **Run the evaluation suite**: record exact commands in plan.md.
4. **Record results** in the HCS (gate outcomes, token spend, wall-clock).
5. **Write a session trace** (see `.agent/docs/telemetry-contract.md`).
6. **Fill in Telemetry section** of the HCS with the trace location and completeness.
7. **Run full verify**: `make verify`.
8. **Fill in Verification Gates section** of the HCS.
9. **Produce an operational review**: `cp .agent/templates/operational-review.md
   .agent/eval/review-<run_id>.md` and fill it in.
10. **Update the readiness report**: `make harness-report`.

---

## Verify Gate

```
make verify                                             # full gate passes
local-agent-harness report --check-no-regression .agent/eval/readiness.md
```

---

## Completion Criteria

- HCS is complete with no `<placeholder>` fields remaining.
- Trace completeness is `complete` (not `missing`).
- `make verify` exits 0.
- Readiness no-regression check passes.
- Operational review is filled in and committed.
- Any waived gate has a reviewed justification with owner and expiry date.

---

## Invariants

- A run claiming a positive verdict cannot have `Trace completeness: missing`.
- Two evaluation runs are comparable only if their HCS fields match on:
  runtime version, model backend/version, AGENTS.md revision, and permission profile.
