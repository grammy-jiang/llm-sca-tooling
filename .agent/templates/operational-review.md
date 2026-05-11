# Operational Review

> Copy to `.agent/eval/review-<run_id>.md` after any significant workflow run.
> Used to assess trace completeness, policy compliance, budget behaviour,
> and improvement candidates.

---

## Identification

| Field | Value |
|---|---|
| Run ID | `<run_id>` |
| Review date | `<ISO-8601>` |
| Reviewer | `<name>` |
| HCS reference | `.agent/eval/hcs-<run_id>.md` |

---

## Trace Completeness

| Check | Result |
|---|---|
| `session_start` present | Yes / No |
| `session_end` present | Yes / No |
| All tool calls logged | Yes / No / Partial |
| All verification events logged | Yes / No / Partial |
| Redaction correctly applied | Yes / No / Unknown |
| **Overall** | **complete \| incomplete \| missing** |

---

## Policy Compliance

| Check | Result |
|---|---|
| All tool calls within permission mode | Yes / No |
| All writes within path allowlist | Yes / No |
| No HC1–HC6 violations | Yes / No |
| Policy violations recorded | `<count and description, or "none">` |
| **Overall** | **compliant \| noncompliant** |

---

## Budget Behaviour

| Budget | Used | Limit | Status |
|---|---|---|---|
| Token spend | `<tokens>` | `250 000` | within / warning / hard-stop |
| Retry budget | `<count>` | `3 per call` | within / warning / hard-stop |
| Wall-clock | `<HH:MM>` | `45 min` | within / warning / hard-stop |
| Compaction events | `<count>` | — | — |
| **Overall** | | | **within-budget \| soft-warning \| hard-stop** |

---

## Anomalies

| Anomaly | Detected? |
|---|---|
| Repeated identical tool calls (≥5) | Yes / No |
| Repeated failing gate | Yes / No |
| Context growth without new evidence | Yes / No |
| Denied-operation storm | Yes / No |
| Stale or mixed snapshot evidence used | Yes / No |
| Out-of-scope write attempted | Yes / No |
| Missing required verification | Yes / No |
| Additional anomalies | `<description or "none">` |

---

## Gate Adequacy

| Field | Value |
|---|---|
| Required gates ran | Yes / No / Partial |
| Gate results (per gate) | `<pass/fail/skip list>` |
| Missing gates | `<list or "none">` |

---

## Incidents

| Field | Value |
|---|---|
| Incidents opened | `<count and IDs, or "none">` |
| Open incidents unresolved | Yes / No |

---

## Promotion Candidates

| Field | Value |
|---|---|
| Improvement candidates identified | `<count and short descriptions, or "none">` |
| Reviewed before promotion | Yes / No / N/A |

---

## Overall Verdict

`process-compliant` | `process-noncompliant` | `trace-incomplete` | `budget-exhausted` | `needs-readiness-work`

**Verdict**: `<verdict>`

**Notes**: `<free text>`
