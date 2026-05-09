# GitHub Copilot Instructions

<!-- Copilot-specific supplement to AGENTS.md.                               -->
<!-- Project overview, setup, test, lint, conventions, security, and quality  -->
<!-- gates are in AGENTS.md — the shared spine read natively by the Copilot  -->
<!-- Cloud Agent. Do not duplicate those sections here.                       -->

## Copilot-specific guidance

- **Code review focus:** flag untyped signatures, missing `# type: ignore`
  justifications, skipped Bandit findings, and any new network egress in
  `src/`. Treat SAST suppressions as high-priority review items.
- **Suggestions:** prefer Ruff-compatible idioms; avoid introducing
  dependencies outside `pyproject.toml` `[project.dependencies]` or `[dev]`.
- **PR summaries:** include change summary, risks, and verification evidence
  (`make verify` output). Note any new or changed dependencies explicitly.
- **Context window:** always refer to `AGENTS.md` for quality gates, scope
  boundaries, hard constraints (HC1–HC6), and the PR checklist before
  proposing changes.

## Notes

- `.agent/eval/` is gitignored; readiness reports are local only.
- Agent harness commands: `local-agent-harness check --repo .` and
  `local-agent-harness validate --repo .`

