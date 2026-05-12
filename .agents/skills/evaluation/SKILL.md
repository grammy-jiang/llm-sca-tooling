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
  version: "1.1.0"
---

# evaluation

## Workflow Control

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Copy and start HCS | deterministic | Yes | `hcs-<run_id>.md` |
| Run evaluation suite | deterministic | Yes — block on failure | benchmark results |
| Record raw results in HCS | deterministic | Yes | `hcs-<run_id>.md` (updated) |
| Write session trace | deterministic | Yes — block if trace missing | `trace.jsonl` |
| Run full verify | deterministic | Yes | exit code |
| Run readiness audit (MCP) | deterministic (MCP-backed) | Yes — block on regression | `readiness_report.json` |
| Produce operational review | llm-reasoning (synthesis) | — | `review-<run_id>.md` |

**Failure policy:** any deterministic step failure stops the run; HCS must not be
marked complete if trace is missing or readiness shows per-axis regression.

**Final synthesis boundary:** the operational review (`review-<run_id>.md`) must
be written after — and only from — `hcs-<run_id>.md`, benchmark results, and
`readiness_report.json`. It must not introduce findings absent from those artifacts.

## Artifact Handoff

```
hcs-<run_id>.md (identification, runtime/model, manifest state filled)
  -> benchmark results (exact commands recorded in plan.md)
  -> hcs-<run_id>.md (gate outcomes, token spend, wall-clock filled)
  -> trace.jsonl (session telemetry, completeness = complete)
  -> exit code from make verify
  -> readiness_report.json (from run_readiness_audit via MCP)
  -> review-<run_id>.md (operational review — read-only synthesis)
```

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
   **Failure policy:** trace completeness must be `complete`; if missing, mark HCS as incomplete and stop.
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

   Save response as `.agent/artifacts/readiness_report.json`.
   **Failure policy:** any per-axis regression blocks Step 11.

10. **Fill Readiness section** of HCS from `run_readiness_audit` response
11. **Produce operational review** — **LLM-reasoning (final synthesis):**

    ```yaml
    step_id: operational-review
    required_inputs:
      - .agent/eval/hcs-<run_id>.md              # gate outcomes and scores
      - .agent/artifacts/readiness_report.json   # per-axis readiness
      - benchmark results                         # from plan.md
    allowed_tools: [read_file]
    forbidden_actions: [run_commands, edit_source, run_tests]
    evidence_requirements:
      - every finding must cite the artifact and field it originates from
      - facts confirmed from artifacts; assumptions labeled separately
    output_structure:
      confirmed_findings: []
      assumptions_and_uncertainties: []
      recommended_follow_up: []
    failure_policy: {on_missing_prerequisite_artifact: block}
    ```

    `cp .agent/templates/operational-review.md .agent/eval/review-<run_id>.md` and fill it in.

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
- Operational review cites only artifacts from this run
- Any waived gate has a reviewed justification with owner and expiry date

## Invariants

- A run claiming a positive verdict cannot have `Trace completeness: missing`
- Two runs are comparable only if HCS fields match on: runtime version, model backend/version, AGENTS.md revision, and permission profile
