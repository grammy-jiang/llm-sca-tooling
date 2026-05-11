# Incident Record

> Copy to `.agent/eval/incident-<incident_id>.md` when a P0 or P1 failure occurs.
> P0 and P1 incidents require all follow-up fields to be filled before closure.

---

## Identification

| Field | Value |
|---|---|
| Incident ID | `INC-<YYYY-NNNN>` |
| Date opened | `<ISO-8601>` |
| Severity | `P0 \| P1 \| P2 \| P3` |
| Status | `open \| contained \| closed` |

---

## Impact

| Field | Value |
|---|---|
| Systems / workflows affected | `<list>` |
| User or data scope | `<description>` |
| Estimated duration | `<HH:MM or "ongoing">` |

---

## Timeline

| Milestone | Timestamp |
|---|---|
| Detection time | `<ISO-8601>` |
| Containment time | `<ISO-8601 or "not yet">` |
| Remediation time | `<ISO-8601 or "not yet">` |
| Incident closed | `<ISO-8601 or "not yet">` |

---

## Root Cause

| Field | Value |
|---|---|
| Proximate cause | `<one-sentence description>` |
| Contributing factors | `<list>` |
| Evidence links | `run_id: <>, event_id: <>, artefact_id: <>` |

---

## Containment

| Field | Value |
|---|---|
| Immediate action taken | `<description>` |
| Blast radius bounded by | `<mechanism: circuit breaker, manual stop, rollback, etc.>` |

---

## Remediation

| Field | Value |
|---|---|
| Fix applied | `<description or PR link>` |
| Verification that fix is effective | `<test run, gate result, or evidence>` |
| Rollback path if fix fails | `<description>` |

---

## Follow-Up (required for P0/P1)

| Item | Status |
|---|---|
| Detector or eval regression created | Yes / No / N/A |
| Static-analysis rule created | Yes / No / N/A |
| Memory or policy update | Yes / No / N/A |
| Readiness task added | Yes / No / N/A |

---

## Reviewer Closure

| Field | Value |
|---|---|
| Reviewer | `<name>` |
| Closed date | `<ISO-8601>` |
| Residual risk accepted | `<description or "none">` |
