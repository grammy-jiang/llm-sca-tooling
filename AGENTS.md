# AGENTS.md

> Agent instructions for this repository.
> See also: `.agent/plan.md` (session plan).

<!-- local-agent-harness:auto:begin -->
<!-- stack: Python -->
## Setup

```bash
pip install -e '.[dev]'
```

## Testing

```bash
pytest
pytest path/to/test_file.py::test_function_name
```

<!-- local-agent-harness:auto:end -->

## Conventions

- Branch naming: `agent/<task-slug>`
- Commit style: Conventional Commits
- Keep functions small and single-purpose.
- Match the existing code style and patterns already in use.
- Prefer explicit error handling over silent failures.
- Run the test suite and linter after every change.
- Never push directly to `main`; always open a pull request.
- `.gitignore` has a managed section below the `# local-agent-harness` marker — do not hand-edit that section.

## Scope Boundary

| Action | Allowed scope |
|---|---|
| Read   | entire repo |
| Edit   | `src/`, `tests/`, `docs/`, `.agent/plan.md` |
| Create | within edit scope |
| Delete | requires human approval |
| Execute | see `.agent/policies/commands.allowlist` |

## Security and Hard Constraints

All hard constraints are enforced at every stage and may never be relaxed.

- **HC1** — No plaintext secrets in repository, prompts, logs, or commits.
- **HC2** — No writes outside the repository working tree.
- **HC3** — Destructive commands (`rm -rf`, `git push --force`, schema drops,
  package publishes) require explicit human approval.
- **HC4** — Migrations and irreversible operations may be authored but never
  executed by the agent.
- **HC5** — Network egress is denied by default; allowlist in `AGENTS.md`.
- **HC6** — Red-class data (secrets, PII, customer data) never enters prompts,
  tool arguments, or logs.

**Data classification:**

| Class | Examples | In prompts? | In logs? |
|---|---|---|---|
| Green | OSS source, public docs | yes | yes |
| Amber | Internal source, non-PII configs | yes (redact tokens) | redacted |
| Red | Secrets, PII, customer data, keys | **no** | **no** |

Use `gitleaks` pre-commit hook. Run the harness validation gate before every PR.

## Stop Conditions

Applies to all agents:

- Doom-loop: if the same tool is called 5× with similar args, stop and ask.
- Out-of-scope write: abort + revert + report.

## PR Checklist

1. All tests pass; add tests for every new function and every bug fix.
2. Linter and formatter clean.
3. No new secrets or SAST findings.
4. PR description: change summary, risks, verification evidence; call out any dependency changes explicitly.
5. Keep PRs small and focused; split unrelated changes into separate PRs.
6. Append a `Decisions log` entry in `.agent/plan.md` for non-trivial choices.
