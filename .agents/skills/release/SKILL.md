---
name: release
description: >
  Prepare and gate a package release with T1–T4 evaluation, readiness checks,
  and incident verification. Use when asked to prepare a release, cut a release,
  bump a version for publication, tag a release, or when a release process needs
  to be formally gated. Requires explicit human approval for git tag and publish
  (HC3 — destructive operation). Uses the llm-sca-tooling MCP server for
  readiness and drift checks.
compatibility: >
  Requires Python 3.12+, uv, and the llm-sca-tooling package. All T1–T4 gates
  must pass. No open P0/P1 incidents allowed. MCP server for readiness:
  `uv run llm-sca-tooling mcp serve --transport stdio`
license: MIT
metadata:
  mcp-server: llm-sca-tooling
  version: "1.1.0"
---

# release

## Workflow Control

| Step | Kind | Blocks downstream? | Artifact output |
|---|---|---|---|
| Check incident log | deterministic | Yes — block on open P0/P1 | `incident_check.txt` |
| Run readiness audit (MCP) | deterministic (MCP-backed) | Yes — block on regression or relaxed drift | `readiness_report.json` |
| Copy and fill HCS | deterministic | Yes | `hcs-release-<version>.md` |
| T1: `make verify` | deterministic | Yes | exit code |
| T2: harness regression tests | deterministic | Yes | exit code |
| T3: integration tests (S2+) | deterministic | Yes if applicable | exit code |
| T4: benchmark suite (S3+) | deterministic | Yes if applicable | benchmark results |
| Record gate results in HCS | deterministic | Yes | `hcs-release-<version>.md` (updated) |
| Write session trace | deterministic | Yes — block if missing | `trace.jsonl` |
| Bump version | deterministic | Yes | `pyproject.toml` diff |
| Tag release | deterministic (HC3 — human approval required) | Yes | `git tag v<version>` |
| Produce operational review | llm-reasoning (final synthesis) | — | `review-release-<version>.md` |
| Publish | deterministic (HC3/HC4 — human execution required) | — | published package |
| Update supply-chain ledger | deterministic | Yes | `.agent/eval/supply-chain-ledger.yaml` |

**Failure policy:** any gate failure blocks all downstream steps.
Steps requiring HC3 approval must not be executed autonomously.

**Final synthesis boundary:** the operational review must be written after all
gate artifacts exist and must not introduce findings absent from those artifacts.

## Artifact Handoff

```
incident_check.txt
  -> readiness_report.json
  -> hcs-release-<version>.md (identification, gate outcomes)
  -> gate exit codes / benchmark results
  -> trace.jsonl
  -> review-release-<version>.md (final synthesis — read-only from above)
```

## Preconditions

- All planned features for the release are merged and green in CI
- `make verify` passes on the release branch
- No open P0 or P1 incidents
- No `relaxed` drift detected (check via `run_readiness_audit`)

## Pre-flight

1. **Check incident log**: confirm no open P0/P1 incidents; record result in `incident_check.txt`
   **Failure policy:** any open P0/P1 blocks all further steps.

2. **Run readiness audit via MCP** (replaces `local-agent-harness check`):

   ```bash
   uv run llm-sca-tooling mcp serve --transport stdio
   ```
   ```json
   {"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"llm-sca-tooling"}},"id":1}
   ```

   Save response as `.agent/artifacts/readiness_report.json`.
   **Failure policy:** any per-axis regression or `relaxed` drift blocks all further steps.

3. **Copy and fill HCS**: `cp .agent/templates/harness-condition-sheet.md .agent/eval/hcs-release-<version>.md`; fill all fields

## Evaluation Gates (T1–T4)

| Tier | Gate | Required |
|---|---|---|
| T1 | `make verify` (format, lint, type-check, unit tests, secrets, SAST, audit) | Always |
| T2 | `uv run pytest tests/harness/ -x` (manifest regression + non-relaxation) | Always |
| T3 | Integration tests (Phase 2+) | S2+ |
| T4 | Evaluation benchmark suite (Phase 3+) | S3 |

## Release Steps

4. **Run T1 gate**: `make verify`
5. **Run T2 gate**: `uv run pytest tests/harness/ -x`
6. **Run T3/T4 gates** if applicable
7. **Record all gate results** in the HCS
8. **Write session trace** and fill HCS Telemetry section
   **Failure policy:** trace completeness must be `complete`; block tag/publish if missing.
9. **Bump version** in `pyproject.toml` and commit
10. **Tag the release**: `git tag v<version>` — **requires explicit human approval (HC3)**
11. **Produce operational review** — **LLM-reasoning (final synthesis):**

    ```yaml
    step_id: release-operational-review
    required_inputs:
      - .agent/eval/hcs-release-<version>.md
      - .agent/artifacts/readiness_report.json
      - gate exit codes / benchmark results
    allowed_tools: [read_file]
    forbidden_actions: [run_commands, edit_source, run_tests, git_tag, publish]
    evidence_requirements:
      - every finding must cite artifact and field
      - confirmed facts separated from assumptions
    output_structure:
      confirmed_findings: []
      assumptions_and_uncertainties: []
      recommended_follow_up: []
    failure_policy: {on_missing_prerequisite_artifact: block}
    ```

    Fill `.agent/templates/operational-review.md` and save as `review-release-<version>.md`.

12. **Publish** — **requires human execution (HC3/HC4)**
13. **Update supply-chain ledger** with the new release version

## Verify Gate

```bash
make verify
uv run pytest tests/harness/ -x
# run_readiness_audit via MCP  # no per-axis regression
```

> Use `run_readiness_audit` via the llm-sca-tooling MCP server instead of
> `local-agent-harness` for drift and readiness checks.

## Completion Criteria

- All T1–T4 gates pass (T3/T4 only if applicable for the stage)
- HCS is complete; trace completeness is `complete`
- No open P0/P1 incidents
- Operational review cites only artifacts from this run
- Tag and publish executed by human (HC3 compliance confirmed)
- Readiness no-regression confirmed via `run_readiness_audit`
- Tag and publish required **human approval (HC3)**; not executed autonomously
- Operational review filed and committed
