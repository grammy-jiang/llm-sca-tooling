# Session Plan - docs-audit-findings-fix-plan

> Ephemeral but auditable. Updated during the session.

## Inputs
- Task statement: Write a separate markdown document under `docs/` with the
  fix plan for the actual docs audit findings, not the stalled-step review.
- Skill: `audit`
- Repo: `/home/grammy-jiang/Documents/evidence-sca`
- Session start: 2026-05-17T21:18:00+10:00

## Non-goals
- Do not implement the fixes in this session.
- Do not modify source, tests, workflows, lockfiles, or scanner baselines.
- Do not execute destructive commands, publish packages, tag releases, or push.

## Allowed scope
- Files: `.agent/plan.md`, `docs/docs-audit-findings-fix-plan.md`
- MCP tools: `register_repo`, `run_readiness_audit`
- Shell commands: `git status`, `git diff`, `sed`, `make verify`

## Proposed steps
1. Read the prior MCP-backed docs audit artifacts.
2. Refresh readiness context with MCP tooling.
3. Write a separate docs fix-plan document covering the audit findings:
   partial compliance, unknown clauses, hidden governance path indexing, missing
   exact Markdown evidence, and `.codex/INSTRUCTIONS.md` drift.
4. Run `make verify`, then revert generated out-of-scope churn if it appears.
5. Summarize changed files, verification, and remaining risk.

## Verification
- [x] Prior audit artifacts reviewed.
- [x] MCP readiness audit refreshed:
  `readiness-audit:3AaZL3XsWxXkQVZ3NUAyqfGc`, Stage S3, score 22, drift
  finding: `.codex/INSTRUCTIONS.md does not restate HC controls`.
- [x] Fix-plan document written:
  `docs/docs-audit-findings-fix-plan.md`.
- [x] `make verify` completed: all gates passed.

## Policy events
- 2026-05-17 - `make verify` modified `.secrets.baseline` and `uv.lock`,
  which are outside this task's write scope. Reverted both with `git restore`.
  Remaining intended changes are limited to `.agent/plan.md` and
  `docs/docs-audit-findings-fix-plan.md`, plus pre-existing prior audit
  artifacts and the earlier stalled-step review document.

## Decisions log
- 2026-05-17 - Corrected the requested scope from stalled-step remediation to
  remediation planning for the actual docs audit findings.
