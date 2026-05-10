# Quickstart

Create a workspace and run the core smoke path:

```bash
uv run llm-sca-tooling config validate
uv run llm-sca-tooling run create demo --run-dir .agent/runs
uv run llm-sca-tooling check-drift . --stage S3
uv run llm-sca-tooling mcp start --workspace .llm-sca
```

Build graph evidence from a repository:

```bash
uv run evidence-sca graph-build .
uv run evidence-sca graph-update .
```

Replay and incident commands operate on the SQLite workspace run ledger:

```bash
uv run llm-sca-tooling replay run:example --workspace .llm-sca --output-format json
uv run llm-sca-tooling diagnose incident:example --workspace .llm-sca
```

Record the HarnessConditionSheet identifier in the run or PR evidence whenever
the output is used as release evidence.

## Limitations

The quickstart uses local storage and local MCP smoke tests. It does not replace
the full `make verify` gate or human review for destructive ledger deletion.
