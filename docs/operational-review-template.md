# Operational Review Template

## Run ID

## Review Date

## Reviewer

## Trace Completeness

- session_start present: Yes | No
- session_end present: Yes | No
- All tool calls logged: Yes | No | Partial
- All verification events logged: Yes | No | Partial
- Redaction correctly applied: Yes | No | Unknown
- Overall: complete | incomplete | missing

## Policy Compliance

- All tool calls within permission mode: Yes | No
- All writes within path allowlist: Yes | No
- No HC1-HC6 violations: Yes | No
- Policy violations recorded:
- Overall: compliant | noncompliant

## Budget Behaviour

- Token budget used:
- Retry budget used:
- Wall-clock budget used:
- Budget hard stops triggered: Yes | No
- Compaction events:
- Overall: within-budget | soft-warning | hard-stop

## Anomalies

- Repeated identical tool calls: Yes | No
- Repeated failing gate: Yes | No
- Context growth without new evidence: Yes | No
- Denied-operation storm: Yes | No
- Stale or mixed snapshot evidence used: Yes | No
- Out-of-scope write attempted: Yes | No
- Missing required verification: Yes | No

## Gate Adequacy

- Required gates ran: Yes | No | Partial
- Gate results:
- Missing gates:

## Incidents

- Incidents opened:
- Open incidents unresolved: Yes | No

## Promotion Candidates

- Improvement candidates identified:
- Reviewed before promotion: Yes | No

## Overall Verdict

`process-compliant | process-noncompliant | trace-incomplete | budget-exhausted | needs-readiness-work`
