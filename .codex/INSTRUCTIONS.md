<!-- .codex/INSTRUCTIONS.md                                                   -->
<!-- Codex CLI-specific supplements.  Codex reads AGENTS.md natively.         -->
<!-- This file adds only Codex CLI-specific behaviour.                         -->

## Codex-specific settings

- Default approval mode: `suggest` (confirm each edit before writing).
- Max turns per session: 40.
- Sandbox: devcontainer (see `.devcontainer/devcontainer.json`).
- Session transcripts: `.agent/logs/`.

## Hard constraints (non-relaxation)

This overlay defers to `AGENTS.md` for all hard constraints.  The Codex CLI
must honour the authoritative HC1–HC6 controls declared there.  Any apparent
conflict between this file and `AGENTS.md` resolves in favour of `AGENTS.md`
(non-relaxation rule).

- **HC1** — No plaintext secrets in repository files, prompts, logs, or
  commits.  `detect-secrets` pre-commit hook and `.secrets.baseline` are
  required.
- **HC2** — No agent-authored writes outside the path allowlist in
  `AGENTS.md` § Scope Boundary.  Out-of-scope writes must be denied,
  reverted, and recorded as policy violations.
- **HC3** — Destructive commands (`rm -rf`, `git push --force`,
  `git reset --hard`, schema drops, package publishes) require explicit
  human approval before execution.
- **HC4** — Database migrations, schema drops, and irreversible
  infrastructure changes must be authored but never executed autonomously.
- **HC5** — Network egress is denied by default; only the destinations
  explicitly listed in `AGENTS.md` may be accessed from agent-executed code.
- **HC6** — Red-class data (secrets, PII, credentials, session tokens,
  customer data) must never enter prompts, tool arguments, trace logs, plan
  files, or stored artefacts.

This overlay may specialise behaviour but must never relax any HC1–HC6 rule
above, nor any other quality gate declared in `AGENTS.md`.

<!-- Stop conditions are defined in AGENTS.md (shared spine). -->
