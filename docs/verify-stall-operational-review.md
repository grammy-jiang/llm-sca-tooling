# Verify Stall Operational Review

Date: 2026-05-17

## Scope

This review covers the stalled-looking steps observed during the docs audit run.
The goal is to explain what happened and define a fix plan that helps future
agents decide when to ignore, skip, prevent, or escalate the same behavior.

## Findings

### 1. The verify gate looked stalled, but completed successfully

Two `make verify` runs appeared quiet for several minutes after this step:

```bash
uv run detect-secrets scan --baseline .secrets.baseline
```

Both runs later completed and printed:

```text
verify: all gates passed
```

The later output showed that the remaining gates had continued through
`pip-audit` and `bandit`. This means the apparent stall was a silent
long-running scanner phase, not a failed verification gate.

Operational impact:

- The operator could not distinguish "still scanning" from "hung" from the
  visible output alone.
- The assistant nearly interrupted a valid gate because the command had no
  heartbeat output.

### 2. Scanner output is too coarse for long-running gates

`make verify` prints each high-level command, but some subcommands do not emit
progress while running. In this run, the visible output stopped at
`detect-secrets`, then later resumed with dependency and SAST results.

Likely contributors:

- `detect-secrets`, `pip-audit`, and `bandit` are mostly quiet until they finish.
- Non-interactive command execution can buffer output.
- The verify target does not print timestamps, elapsed time, or per-step
  heartbeat messages.

### 3. The command session could not be interrupted cleanly

An attempted interrupt failed because the running command session had closed
stdin. That means a long-running non-TTY verification command may be difficult
to stop from the assistant side once started.

Operational impact:

- If a gate actually hangs, the agent may need a separate process-management
  path rather than a clean Ctrl-C.
- Future long-running verification commands should be started in a mode that
  supports interruption or should enforce their own timeout.

### 4. Verification produced out-of-scope generated churn

The prior audit run produced tracked changes outside the allowed audit scope:

- `.llm-sca/`
- `.secrets.baseline`
- `uv.lock`

Those changes were reverted with `git restore`. The final intended changes were
limited to `.agent/plan.md`, `.agent/artifacts/`, and this follow-up `docs/`
report.

Operational impact:

- The repository currently mixes required verification commands with commands
  that can mutate tracked state.
- The governance scope did not allow those writes for the docs audit, so they
  became HC2 cleanup work.

### 5. MCP graph evidence was weak for exact verify-step diagnosis

The MCP relevance lookup found general harness and docs material, but did not
return exact Makefile or scanner spans for the stalled-looking verify step. This
is an observability gap: operational investigations need direct evidence for
the verify target and its subcommands.

## What To Ignore, Skip, Prevent, Or Escalate

### Ignore

Ignore a quiet verify phase when all of these are true:

- The command has been quiet for less than the configured scanner timeout.
- The previous printed step is a known quiet scanner, such as
  `detect-secrets`, `pip-audit`, or `bandit`.
- The process is still alive.
- The total session budget has not been exceeded.

In that case, report it as "scanner phase still running" rather than "stalled".

### Skip

Do not skip `make verify` for completion claims, commits, PRs, or releases.

For docs-only work, add a separate fast precheck target in the future, but keep
full `make verify` as the final gate unless the governance manifest is changed
and reviewed.

Candidate future targets:

```bash
make verify-fast
make verify-docs
make verify-security
```

These should reduce local iteration time without weakening the final gate.

### Prevent

Prevent recurrence by making long-running gates observable and non-mutating:

1. Add timestamps around every `make verify` substep.
2. Add heartbeat output for scanner steps that can run longer than 60 seconds.
3. Split `make verify` into named phases so a stalled phase is visible.
4. Run `uv` in frozen mode for verification so `uv.lock` cannot change.
5. Run secrets checks against a temporary output file or read-only baseline so
   `.secrets.baseline` cannot be updated during verify.
6. Move MCP task/workspace state to an explicitly allowed generated location,
   or add a reviewed allowlist entry for the chosen cache path.
7. Capture verify output to a session log under `.agent/` with start/end times
   and redaction status.
8. Give long MCP tasks a visible heartbeat and final task id in the plan.

### Escalate

Escalate instead of waiting when any of these happen:

- No output for longer than the configured scanner timeout.
- No matching child process is alive.
- The same task is polled five times with no progress change and no heartbeat.
- Verification repeatedly mutates out-of-scope tracked files.
- A gate asks for network egress not allowed by AGENTS.md.
- A scanner reports high/critical findings or secret exposure.

## Fix Plan

### Phase 1 - Documentation and runbook

- Add this report to `docs/`.
- Add a short operator note near the verify instructions explaining that some
  scanner phases are quiet and may take several minutes.
- Define default thresholds:
  - heartbeat interval: 60 seconds
  - scanner soft timeout: 10 minutes
  - scanner hard timeout: 15 minutes

### Phase 2 - Makefile observability

- Wrap every verify substep with a small status line:

```text
[verify] start detect-secrets
[verify] done detect-secrets elapsed=...
```

- Split the target internally:

```makefile
verify: verify-format verify-types verify-tests verify-security
```

- Keep `make verify` as the canonical full gate.

### Phase 3 - Non-mutating verification

- Use frozen dependency execution for verify commands.
- Ensure `detect-secrets` reads the baseline without rewriting it.
- Add a post-verify dirty-state check for known generated files.
- Decide whether `.llm-sca/` is a tracked artifact, an ignored cache, or an
  explicitly allowlisted generated MCP workspace. Do not leave it ambiguous.

### Phase 4 - Agent workflow safeguards

- For long-running verification commands, use a command mode that supports
  interruption or wrap the command with a timeout.
- Record the active substep in `.agent/plan.md` before running long gates.
- If output is silent past the heartbeat interval, check process liveness and
  report the active phase rather than declaring a stall.
- If generated out-of-scope files appear, revert them immediately and record the
  event in the session plan.

## Acceptance Criteria

The fix is complete when:

- `make verify` emits start/end lines for each phase.
- Scanner phases produce heartbeat output or timeout clearly.
- Verify no longer modifies `uv.lock` or `.secrets.baseline`.
- MCP workspace writes are either moved to an allowed generated path or covered
  by a reviewed governance allowlist entry.
- A docs-only precheck exists for fast iteration, while full `make verify`
  remains required for completion claims.
