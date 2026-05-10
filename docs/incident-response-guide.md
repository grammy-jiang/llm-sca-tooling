# Incident Response Guide

Use the operational ledger to diagnose incidents:

```bash
uv run llm-sca-tooling diagnose incident:example --workspace .llm-sca --show-promotion-candidates
uv run llm-sca-tooling replay run:example --workspace .llm-sca --show-events
```

Incident records should include:

- source run and event IDs;
- impact, containment, remediation, and reviewer;
- evidence links, exported ledger bundle, and trace replay notes;
- a HarnessConditionSheet reference when incident lessons influence release
  readiness or durable memory.

Deletion of run or incident ledger records must use the explicit deletion
confirmation path and should normally run as a dry-run first.

## Limitations

The incident workflow is local-ledger focused. It does not page operators, file
external tickets, or perform irreversible cleanup without explicit approval.
