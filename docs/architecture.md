# Architecture

`evidence-sca` stores repository evidence in a local workspace:

- `storage`: SQLite persistence, migrations, graph facts, run records, incidents,
  readiness records, imports, and exports.
- `indexing`, `plugins`, `sarif`, and `traces`: evidence producers.
- `mcp_server`: local tool and resource facade over stored evidence.
- `workflows`, `memory`, `release`, and `hardening`: higher-level governance,
  evaluation, replay, release gates, drift checks, and operational hardening.
- `privacy`, `operations`, and `transport`: retention, redaction, ledger
  export/delete controls, and hardened transport configuration.

Phase 19 keeps operational controls deterministic: permission profiles are typed,
cache invalidation emits auditable events, graph chunking is bounded, and drift
checks produce structured records. Release evidence should include the relevant
HarnessConditionSheet.

## Limitations

The architecture is single-workspace and local-first. Cloud tenancy, hosted
identity, and distributed queueing are explicitly outside this phase.
