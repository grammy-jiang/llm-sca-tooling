# Changelog

All notable changes to `llm-sca-tooling` are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.3.4] — 2026-05-17

### Fixed

#### `setup` subcommand — exclude `agent.md` and `agents/` from Claude Code skills dir

- Skills were not visible in Claude Code because the skill directories
  contained `agent.md` and `agents/openai.yaml` (subagent / Codex metadata
  files) that do not belong in a Claude Code skill.  `shutil.copytree` was
  copying the entire source directory including those files.
- Added `_SKILL_COPY_EXCLUDES` and `_SKILL_COPY_EXCLUDES_CLAUDE` constants to
  drive a per-agent exclude set passed to `shutil.copytree(ignore=...)`.
- **Claude Code** skill dirs now contain only `SKILL.md` and standard
  subdirectories (`references/`, `scripts/`, `assets/`).
- **`~/.agents/skills/`** (Copilot CLI + Codex) keeps `agents/openai.yaml`
  for Codex UI metadata but still strips `agent.md`.
- Manually cleaned the three already-deployed skill dirs
  (`~/.claude/skills/{audit,fix,ship}/`) to remove the extraneous files.

---

## [0.3.3] — 2026-05-17

### Fixed

#### `setup` subcommand — correct skill paths for Codex CLI and Copilot CLI

- **Codex CLI skills**: corrected skill installation path from the previous
  (wrong) assumption that Codex has no skills to the correct
  `~/.agents/skills/` path, confirmed in the official Codex CLI documentation.
  Codex CLI fully supports the
  [Agent Skills open standard](https://agentskills.io).
- **GitHub Copilot CLI skills**: changed skill installation path from the
  invented `~/.copilot/skills/` to `~/.agents/skills/` — the Agent Skills
  standard user-level directory that both Copilot CLI and Codex CLI share.
  Skills are installed once to that shared location and both agents discover
  them automatically.
- **Codex `agents/openai.yaml`**: added `agents/openai.yaml` to each bundled
  skill directory. Codex uses this file for UI metadata (display name, short
  description, invocation policy) and tool dependency declarations in the
  Codex app and CLI plugin browser.

### Changed

#### `setup` subcommand — updated documentation

- Updated module-level docstring and CLI `--help` text to accurately describe
  which skill/MCP/agent paths are written for each AI agent:
  - Claude Code: `~/.claude/skills/`, `~/.claude/agents/`, `~/.claude.json`
  - Copilot CLI: `~/.agents/skills/` (shared), `~/.copilot/agents/`, `~/.copilot/mcp-config.json`
  - Codex CLI: `~/.agents/skills/` (shared), `~/.codex/config.toml`

---

## [0.3.2] — 2026-05-17

### Changed

#### `setup` subcommand — agent detection before installation

- `setup` now detects which AI agents are installed before doing any work:
  - **Claude Code**: checks `shutil.which("claude")`
  - **GitHub Copilot CLI**: checks `shutil.which("gh")` then probes
    `gh copilot --version` (exit 0 = installed)
  - **Codex CLI**: checks `shutil.which("codex")`
- Prints a `FOUND` / `MISS` summary so the user knows exactly what was
  detected and what was skipped.
- Installs skills, sub-agents, and MCP **only for detected agents**.
- Added `--all` flag to bypass detection and configure all three agents
  regardless (useful in CI or when binaries are not on `PATH`).
- **Codex CLI**: correctly skips skills and sub-agents installation —
  Codex only supports MCP (`~/.codex/config.toml`); it has no skills
  or sub-agents directory.
- Removed the now-unnecessary `--skill-root` override option (was only
  needed because setup previously couldn't detect which agents existed).

---



### Fixed

#### `setup` subcommand — agent definition files now installed

- **Root cause**: `setup` previously only installed `SKILL.md` files to
  `~/.claude/skills/`, `~/.copilot/skills/`, `~/.codex/skills/`.  Claude Code
  and Copilot CLI require *separate* sub-agent definition files (different
  directory and naming convention) for agents to appear in `/agents`.
- Added `agent.md` bundled files for each skill (`audit`, `fix`, `ship`).
  Each file has YAML frontmatter with `name`, `description`, `skills:` (to
  preload the corresponding `SKILL.md` into the agent's context), and a concise
  workflow-routing body.
- `setup` now also writes:
  - `~/.claude/agents/<name>.md`        — Claude Code sub-agents
  - `~/.copilot/agents/<name>.agent.md` — GitHub Copilot CLI sub-agents
- Updated `--list` output to show agent file targets alongside skill dirs.
- After running `setup --force`, restart Claude Code and the agents will appear
  in `/agents` and via `/` slash-command routing.

---

## [0.3.0] — 2026-05-17

### Added

#### `setup` CLI subcommand
- New `llm-sca-tooling setup` command installs skills and configures the MCP
  server for all three supported AI agents in one step.
- Options: `--force` (overwrite existing), `--symlink` (symlink instead of
  copy), `--no-mcp` (skip MCP config), `--list` (dry-run list), `--skill-root`.
- Skill data (`audit/`, `fix/`, `ship/`) is now bundled inside the wheel under
  `src/llm_sca_tooling/skill_data/` and located at runtime via
  `importlib.resources`, so the command works from both an editable install and
  an installed wheel.
- MCP server is auto-configured in all three agent config locations:
  - **Claude Code** — `~/.claude.json` (`mcpServers.llm-sca-tooling`)
  - **Copilot CLI** — `~/.copilot/mcp-config.json` (`mcpServers.llm-sca-tooling`)
  - **Codex CLI** — `~/.codex/config.toml` (`[mcp_servers.llm-sca-tooling]`)
- Skills are installed to the per-agent skill directories:
  - `~/.claude/skills/`, `~/.copilot/skills/`, `~/.codex/skills/`

#### Consolidated skills (3 instead of 8)
The original 8 fine-grained skills were merged into 3 memorable, high-level
skills to reduce cognitive load for end users.

| New skill | Replaces |
|---|---|
| `audit` | `architecture-compliance`, `code-audit` |
| `fix` | `sast-repair`, `test-first-repair`, `safe-refactor` |
| `ship` | `dependency-update`, `evaluation`, `release` |

Each skill's `SKILL.md` includes a routing table so the agent selects the right
workflow automatically based on the user's request.

#### MCP tool tier filtering
Tools in the MCP server are now grouped into four tiers to control which tools
are visible by default:

| Tier | Count | Description |
|---|---|---|
| 1 | 8 | Primary workflow launchers (always visible) |
| 2 | 9 | Infrastructure / async-polling helpers |
| 3 | 13 | Evidence / query tools (internal plumbing) |
| 4 | 16 | Operational harness governance tools |

**Default** (`tools/list` with no special capabilities): **17 tools** (Tier 1 + 2).

To request the full surface of 47 tools, pass in the `initialize` request:
```json
{
  "clientInfo": {
    "capabilities": {"tool_tiers": [1, 2, 3, 4]}
  }
}
```

Implementation details:
- `ToolDescriptor` gained a `tier: int = 1` field.
- `ToolRegistry.list_descriptors_for_tiers(tiers)` filters by tier set.
- `MCPServer.initialize()` reads `tool_tiers` from `client_capabilities` and
  stores the negotiated set; `list_tools()` applies the filter.
- `stdio_transport.py` extracts `clientInfo.capabilities` (and top-level
  `capabilities`) from the MCP `initialize` frame and passes them to
  `server.initialize()`.

### Changed
- `pyproject.toml`: added `.agent/` to the `[tool.black]` exclude list to
  prevent Black from touching agent plan and lesson files.
- `evolve_static_rules` MCP tool is now **opt-in** via the
  `LLM_SCA_EVOLVE_RULES` environment variable (set to `1`, `true`, or `yes`).
  The tool is absent from `tools/list` by default even when Tier 4 is
  requested, because the architecture doc marks it "optional offline" (§2.1).
  Default `tools/list` with `tool_tiers: [1,2,3,4]` now returns **46 tools**;
  with `LLM_SCA_EVOLVE_RULES=1` it returns **47 tools**.

### Removed
- Old 8 skill directories from `.agents/skills/` and
  `src/llm_sca_tooling/skill_data/` (`architecture-compliance`, `code-audit`,
  `dependency-update`, `evaluation`, `release`, `safe-refactor`, `sast-repair`,
  `test-first-repair`).

---

## [0.2.0] — 2025 (prior releases)

See git log for earlier changes: `git log --oneline v0.2.0`.
