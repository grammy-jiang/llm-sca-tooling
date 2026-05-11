# Incident Response Guide

> This guide covers how to open, diagnose, and close incidents in `evidence-sca`.
> For harness setup and permission profiles, see [Harness Setup Guide](harness-setup-guide.md).

---

## Limitations

- Incident diagnosis is based on run records and operational ledger entries alone.
  It does not require access to the original source repository.
- Replay is deterministic for the same run record; it does not re-execute tool calls.
- P0/P1 incidents require human reviewer sign-off. Automated closure is not permitted.
- Lesson promotion requires human review. Automated promotion from incidents is not
  permitted.
- A `HarnessConditionSheet` must be completed before a remediation run is accepted
  as evidence of resolution.

---

## P0 / P1 / P2 Classification

| Class | Meaning | Response time | Human required? |
|---|---|---|---|
| **P0** | HC violation, secrets committed, data leak, out-of-scope write | Immediate | Yes — stop all work |
| **P1** | Release gate failure, calibration regression, budget hard-stop | < 1 hour | Yes |
| **P2** | Harness drift warning, T1 smoke failure, stale artefact | < 24 hours | Recommended |

### P0 criteria (examples)

- Plaintext secret found in a committed file (HC1 violation).
- Agent wrote to a path outside the scope boundary (HC2 violation).
- Destructive command executed without approval (HC3 violation).
- Red-class data found in prompts, logs, or artefacts (HC6 violation).

For any P0: **stop all work immediately, do not push, rotate any exposed credentials,
then open an incident record.**

---

## Opening an Incident

### Via CLI (from a known run ID)

```bash
# The diagnose command reads from the incident store
llm-sca-tooling diagnose incident <incident_id>
```

### Via the incident template

Create `.agent/incidents/<incident_id>.yaml` using the template at
`.agent/templates/incident-record.md`:

```yaml
incident_id: "INC-2026-001"
class: P1
title: "T1 smoke eval regression after Phase 19 release"
run_id: "run-abc123"
impact: "T1 gate fails; CI blocked for all contributors"
timeline:
  - ts: "2026-05-11T10:00:00Z"
    event: "T1 gate started failing on main branch"
  - ts: "2026-05-11T10:05:00Z"
    event: "Incident opened"
root_cause: ""   # fill in after diagnosis
containment: ""
remediation: ""
evidence_links: []
reviewer: ""
closed: false
```

---

## Using `diagnose` for Trace Replay

```bash
# Display incident timeline and root cause
llm-sca-tooling diagnose incident <incident_id>

# Include run event replay
llm-sca-tooling diagnose incident <incident_id> --trace-run

# Show promotion candidates
llm-sca-tooling diagnose incident <incident_id> --show-promotion-candidates

# Output as JSON
llm-sca-tooling diagnose incident <incident_id> --output-format json
```

The `--trace-run` flag invokes `replay run` for the incident's linked `run_id` and
shows the full event sequence inline.

---

## Incident Fields Reference

| Field | Required | Description |
|---|---|---|
| `incident_id` | Yes | Unique identifier (e.g., `INC-2026-001`) |
| `class` | Yes | P0, P1, or P2 |
| `title` | Yes | Short description |
| `run_id` | Yes | The run record linked to this incident |
| `impact` | Yes | Who/what is affected |
| `timeline` | Yes | Chronological list of `{ts, event}` entries |
| `root_cause` | Yes (before close) | Concise statement of root cause |
| `containment` | Yes (before close) | What was done to stop the bleeding |
| `remediation` | Yes (before close) | What was done to fix the root cause |
| `evidence_links` | Recommended | Run IDs, commit SHAs, or artefact paths |
| `detector_follow_up` | Recommended | What detection was added to prevent recurrence |
| `reviewer` | Yes (for P0/P1) | Human reviewer who signs off |
| `closed` | Yes | `false` until reviewer closes |

---

## Linking a Detector Follow-Up

After root cause analysis, add a detector that will catch the same issue in future:

```yaml
detector_follow_up:
  type: "harness_drift_rule"
  description: "Add check: T1 smoke fixture count >= N"
  added_to: ".agent/drift-rules/t1-smoke-count.yaml"
```

Common detector types:
- `harness_drift_rule`: added to drift checker
- `pre_commit_hook`: added to `.pre-commit-config.yaml`
- `ci_gate`: added to `.github/workflows/verify.yml`
- `test_case`: added to `tests/`

---

## Closing an Incident

An incident can only be closed when:

1. `root_cause` is filled in.
2. `containment` and `remediation` are documented.
3. A remediation run has passed all gates (T1 minimum; T2+ for P0/P1).
4. The remediation run's `HarnessConditionSheet` is complete.
5. For P0/P1: a human reviewer has signed off (`reviewer` field populated).

```bash
# Verify remediation run passes
llm-sca-tooling release gate --suite t1

# Then mark incident closed in .agent/incidents/<incident_id>.yaml:
# closed: true
# reviewer: "alice@example.com"
# closed_ts: "2026-05-11T14:00:00Z"
```

---

## Promoting a Lesson

After closing an incident, extract generalizable learnings for the lessons library:

```bash
# Review promotion candidates
llm-sca-tooling diagnose incident <incident_id> --show-promotion-candidates
```

Lessons are promoted from `.agent/plan.md` or incident records to `.agent/lessons/`
after human review. See the lesson promotion policy in `AGENTS.md`.

Lesson format:

```yaml
title: "T1 smoke fixtures must include cross-language fixtures"
body: "Incident INC-2026-001 revealed that T1 smoke only covered Python. Add at least one cross-language fixture to catch plugin regressions."
origin_run_id: "run-abc123"
promoted_by: "alice@example.com"
promoted_ts: "2026-05-11T15:00:00Z"
applies_to: "evaluation"
```

---

## Rollback Path Documentation

Every P0/P1 incident must include rollback path documentation:

```yaml
rollback_path:
  steps:
    - "Revert commit <SHA> using: git revert <SHA>"
    - "Re-run T1 smoke: llm-sca-tooling release gate --suite t1 --null-mode"
    - "Rotate any exposed credentials (if HC1 violation)"
  estimated_time: "15 minutes"
  owner: "on-call engineer"
```

Rollback paths must be documented before an incident is marked P0 or P1.

---

## Quick Reference

```bash
# Open diagnosis
llm-sca-tooling diagnose incident INC-2026-001

# Replay run events
llm-sca-tooling replay run <run_id> --show-events

# Compare two runs
llm-sca-tooling replay run <run_id_a> --diff-run <run_id_b>

# Check harness drift
llm-sca-tooling release check-drift .

# Verify remediation
llm-sca-tooling release gate --suite t1
```

---

## Related Documents

- [Harness Setup Guide](harness-setup-guide.md) — configure HC constraints and drift checks.
- [Evaluation Guide](evaluation-guide.md) — run calibration checks after remediation.
- [Architecture Overview](architecture.md) — understand run records and operational store.
