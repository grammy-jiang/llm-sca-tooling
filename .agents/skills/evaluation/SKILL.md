---
name: evaluation
description: >
  Run a benchmark or regression suite and record a Harness Condition Sheet (HCS).
  Use when asked to evaluate the tooling, run benchmarks, record an evaluation run,
  assess AI-readiness score, or produce an operational review. Also use when
  completing a feature and needing to formally gate it with telemetry and HCS
  evidence. Uses the llm-sca-tooling MCP server for readiness checks.
compatibility: >
  Requires Python 3.12+, uv, and the llm-sca-tooling package. HCS template at
  `.agent/templates/harness-condition-sheet.md`. MCP server for readiness:
  `uv run llm-sca-tooling mcp serve --transport stdio`
license: MIT
metadata:
  mcp-server: llm-sca-tooling
  version: "1.0.0"
---

# evaluation

## Preconditions

- Benchmark or regression suite is defined and reachable
- HCS template available at `.agent/templates/harness-condition-sheet.md`
- `make verify` passes on the current branch before starting
- Evaluation fixture set (if held-out) is available and hash-verified

## Steps

1. **Copy HCS template**: `cp .agent/templates/harness-condition-sheet.md .agent/eval/hcs-<run_id>.md`
2. **Fill identification, runtime/model, and manifest state** in the HCS before running
3. **Run the evaluation suite**: record exact commands in `plan.md`
4. **Record results** in the HCS (gate outcomes, token spend, wall-clock)
5. **Write session trace** (see `.agent/docs/telemetry-contract.md`)
6. **Fill Telemetry section** of the HCS with trace location and completeness
7. **Run full verify**: `make verify`
8. **Fill Verification Gates section** of the HCS
9. **Run readiness audit via MCP** (not external harness):

   ```bash
   uv run llm-sca-tooling mcp serve --transport stdio
   ```

   Then call:
   ```json
   {"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"llm-sca-tooling"}},"id":1}
   ```

10. **Fill Readiness section** of HCS from `run_readiness_audit` response
11. **Produce operational review**: `cp .agent/templates/operational-review.md .agent/eval/review-<run_id>.md` and fill it in

## Verify Gate

```bash
make verify                    # full gate passes
# run_readiness_audit via MCP  # no per-axis regression
```

> Use `run_readiness_audit` via MCP instead of `local-agent-harness report`.

## Completion Criteria

- HCS is complete with no `<placeholder>` fields remaining
- Trace completeness is `complete` (not `missing`)
- `make verify` exits 0
- Readiness no-regression confirmed via `run_readiness_audit`
- Operational review filled in and committed
- Any waived gate has a reviewed justification with owner and expiry date

## Invariants

- A run claiming a positive verdict cannot have `Trace completeness: missing`
- Two runs are comparable only if HCS fields match on: runtime version, model backend/version, AGENTS.md revision, and permission profile
