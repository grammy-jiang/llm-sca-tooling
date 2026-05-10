# Harness Setup Guide

The harness setup requires:

- `AGENTS.md` with hard constraints and command policy.
- `.agent/plan.md` for session trace and decisions.
- `.github/workflows/verify.yml` for the repository verify path.
- A stage record at `.agent/harness-stage.json`.
- A HarnessConditionSheet for release-relevant work.

Run drift checks before a PR:

```bash
uv run llm-sca-tooling check-drift . --stage S3 --report-out .agent/drift-report.json
```

Use permission profiles conservatively. The default Phase 19 set contains
read-only, read-search, read-search-edit, read-search-execute, review, and commit
profiles.

## Limitations

This repo does not allow agents to create `.devcontainer/` directly. A template
for operators is provided in `docs/devcontainer-template.md`.
