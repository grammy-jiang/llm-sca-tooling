<!-- .codex/INSTRUCTIONS.md                                                   -->
<!-- Codex CLI-specific supplements.  Codex reads AGENTS.md natively.         -->
<!-- This file adds only Codex CLI-specific behaviour.                         -->
<!-- Project overview, setup, test, lint, security, and quality gates          -->
<!-- are in AGENTS.md (the shared spine) — do not duplicate here.             -->

## Codex-specific settings

- Default approval mode: `suggest` (confirm each edit before writing).
- Max turns per session: 40.
- Sandbox: devcontainer (see `.devcontainer/devcontainer.json`).
- Session transcripts: `.agent/logs/`.
- Shared hard constraints, quality gates, and path scope in `AGENTS.md` take
  precedence over this overlay.

<!-- Stop conditions and verify commands are defined in AGENTS.md (shared spine). -->
