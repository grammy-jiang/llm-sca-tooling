# CLAUDE.md — Claude Code project instructions

<!-- DRY: shared build commands, conventions, and scope boundary live in  -->
<!-- AGENTS.md.  This file imports it and adds Claude Code-only settings. -->

@AGENTS.md

<!-- claude-code-only: begin -->
## Claude Code–specific behaviour

### Permission ladder
- Default mode: `default`  (switch to `plan` for risky changes)
- Allowed tools: `Read`, `Glob`, `Grep`, `Edit`, `Bash` (allow-listed in
  `.claude/settings.json`)
- Denied tools and paths: see `.claude/settings.json` (authoritative; do not duplicate here)
- MCP servers: none configured by default — add to `.mcp.json`

### When to enter Plan mode
Activate Plan mode (propose before writing) for:
cross-cutting refactors, dependency upgrades, schema / DB migrations, and
any request containing the words *refactor*, *upgrade*, *migrate*, or
*redesign*.

### Compaction
Compact at 70 % of context window.
Always retain: `AGENTS.md`, current `plan.md`, last 5 tool calls, open diff.

### Stop conditions
- If a tool call fails 3× consecutively → stop and ask the user.
<!-- Out-of-scope write behaviour is covered by AGENTS.md § Stop Conditions. -->
<!-- claude-code-only: end -->
