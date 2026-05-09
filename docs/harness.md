# Phase H0 Harness Foundation

Phase H0 defines the operating envelope for `evidence-sca`. It is both a
development contract for repository work and a product contract for later
workflow runs.

## Success Definition

A feature phase is complete only when it can provide:

- A Harness Condition Sheet.
- A live session trace or an explicit trace limitation.
- A passing local verify path.
- Evidence that tool policy, path scope, redaction, and budget controls were
  followed.

## Tool Categories And Permission Modes

Tool categories are `read`, `search`, `edit`, `execute`, `review`, and
`commit`. Permission profiles are deny-first:

- `read-only`: read and search only.
- `plan`: read/search plus `.agent/plan.md` edits.
- `scoped-edit`: edits within the declared path allowlist.
- `scoped-execute`: scoped edits plus allowlisted commands.
- `review-commit`: review and commit operations after gates pass.

Network egress is denied by default. Any exception must be documented in
`AGENTS.md` and recorded in the run or session trace.

## Telemetry Contract

Session traces are JSONL and append-only. Required events include
`session_start`, `session_end`, `plan_created`, `plan_updated`, `tool_call`,
`tool_result`, `context_assembled`, `compaction_event`, `cost_checkpoint`,
`diff_snapshot`, `verification_event`, `human_approval`, `human_rejection`,
`policy_decision`, `budget_warning`, and `budget_hard_stop`.

Every event carries `event_id`, `session_id`, `seq`, `ts`, `type`, `actor`,
`stage`, and `redaction_status`. Tool events also carry `tool_name`,
`tool_category`, `policy_action`, `input_ref`, `output_ref`, `token_count`, and
`wall_ms` where available.

## Run-Record Contract

Product workflows emit append-only run records with `run_id`, workflow, repo
scope, model backend, toolset hash, policy ID, permission profile, context
budget, redaction policy, run-event count, harness condition, final verdict,
and incident links. Run events are sequence-numbered and record actor, stage,
policy action, artefact references, token count, wall time, and redaction
status.

## AI-Readiness

Readiness is scored from 0 to 25 across five axes:

- `agent_config`
- `documentation`
- `ci_cd`
- `code_structure`
- `security`

Stage thresholds are:

- S0 to S1: at least 5 total and at least 1 per axis.
- S1 to S2: at least 12 total and at least 2 per axis.
- S2 to S3: at least 18 total and at least 3 per axis.
- Stable S3: at least 22 total and at least 4 per axis.

Readiness must not regress silently. Any axis drop requires a reviewed waiver
with owner and review date.

## Harness Drift

Drift classes are:

- `missing`: a required artefact does not exist.
- `stale`: an artefact exists but no longer reflects its dependencies.
- `relaxed`: a policy, hard constraint, or gate has been weakened.
- `out-of-stage`: an artefact claims a maturity stage that the repo has not
  reached.
- `clean`: no detected drift.

`relaxed` drift blocks release and higher-autonomy work until reviewed.

## Supply Chain And Provenance

Workflow-relevant runtimes, dependencies, analysers, prompt assets, skills, and
MCP tools must be pinned or provenance-tracked. `uv.lock` is committed as the
Python dependency ledger. Tool and dependency changes trigger dependency and
secret-scan evidence through `uv run pip-audit`, `uv run detect-secrets scan
--baseline .secrets.baseline`, and the compatibility Gitleaks hook expected by
the current local harness validator. SARIF-producing runs record analyser
versions in their Harness Condition Sheet.

## Review Templates

- Harness Condition Sheet: `docs/harness-condition-sheet.md`
- Operational Review: `docs/operational-review-template.md`
- Incident Record: `docs/incident-record-template.md`
