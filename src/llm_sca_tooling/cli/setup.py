"""``llm-sca-tooling setup`` — install skills, agents, and configure MCP servers.

Installs the bundled skills and sub-agent definition files into the global
agent directories and registers the ``llm-sca-tooling`` MCP server in the
configuration files for each agent (GitHub Copilot CLI, Claude Code, and
Codex CLI).

Agent skill roots
-----------------
* ``~/.claude/skills/``   — Claude Code
* ``~/.copilot/skills/``  — GitHub Copilot CLI
* ``~/.codex/skills/``    — Codex CLI / OpenAI Codex

Agent sub-agent definition files
---------------------------------
* ``~/.claude/agents/<name>.md``            — Claude Code  (YAML frontmatter + body)
* ``~/.copilot/agents/<name>.agent.md``     — GitHub Copilot CLI

MCP server configuration
------------------------
* Claude Code    → ``~/.claude.json``          (user-scope, all projects)
* Copilot CLI    → ``~/.copilot/mcp-config.json``
* Codex CLI      → ``~/.codex/config.toml``

The MCP stdio command registered is::

    llm-sca-tooling mcp serve

which uses the default stdio transport.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import typer

from llm_sca_tooling.skill_data._paths import SKILL_NAMES, skill_data_root

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MCP_SERVER_NAME = "llm-sca-tooling"
_MCP_COMMAND = "llm-sca-tooling"
_MCP_ARGS: list[str] = ["mcp", "serve"]

# Agent skill root directories (relative to ~/)
_SKILL_ROOTS: dict[str, Path] = {
    "claude": Path.home() / ".claude" / "skills",
    "copilot": Path.home() / ".copilot" / "skills",
    "codex": Path.home() / ".codex" / "skills",
}

# Agent sub-agent definition directories (relative to ~/)
_CLAUDE_AGENTS_DIR = Path.home() / ".claude" / "agents"
_COPILOT_AGENTS_DIR = Path.home() / ".copilot" / "agents"

# ---------------------------------------------------------------------------
# Skill installation helpers
# ---------------------------------------------------------------------------


def _install_skill(src: Path, dst: Path, *, symlink: bool, force: bool) -> str:
    """Copy or symlink *src* → *dst*.  Return a status message."""
    if dst.exists() or dst.is_symlink():
        if not force:
            return f"SKIP   {dst}  (exists; use --force to overwrite)"
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if symlink:
        dst.symlink_to(src, target_is_directory=True)
        return f"LINK   {dst} -> {src}"
    shutil.copytree(src, dst)
    return f"COPY   {dst}"


def _install_skills(
    skill_roots: list[Path], *, symlink: bool, force: bool
) -> list[str]:
    """Install all bundled skills into every requested root."""
    data_root = skill_data_root()
    messages: list[str] = []
    for skill_name in SKILL_NAMES:
        src = data_root / skill_name
        for root in skill_roots:
            dst = root / skill_name
            messages.append(_install_skill(src, dst, symlink=symlink, force=force))
    return messages


# ---------------------------------------------------------------------------
# Agent definition file installation helpers
# ---------------------------------------------------------------------------


def _install_agent_file(src: Path, dst: Path, *, force: bool) -> str:
    """Copy *src* → *dst*.  Return a status message."""
    if dst.exists():
        if not force:
            return f"SKIP   {dst}  (exists; use --force to overwrite)"
        dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return f"AGENT  {dst}"


def _install_claude_agents(*, force: bool) -> list[str]:
    """Install agent definition files into ``~/.claude/agents/``."""
    data_root = skill_data_root()
    messages: list[str] = []
    for skill_name in SKILL_NAMES:
        src = data_root / skill_name / "agent.md"
        if not src.exists():
            messages.append(f"WARN   {src} not found, skipping")
            continue
        dst = _CLAUDE_AGENTS_DIR / f"{skill_name}.md"
        messages.append(_install_agent_file(src, dst, force=force))
    return messages


def _install_copilot_agents(*, force: bool) -> list[str]:
    """Install agent definition files into ``~/.copilot/agents/``."""
    data_root = skill_data_root()
    messages: list[str] = []
    for skill_name in SKILL_NAMES:
        src = data_root / skill_name / "agent.md"
        if not src.exists():
            messages.append(f"WARN   {src} not found, skipping")
            continue
        dst = _COPILOT_AGENTS_DIR / f"{skill_name}.agent.md"
        messages.append(_install_agent_file(src, dst, force=force))
    return messages


_CLAUDE_JSON = Path.home() / ".claude.json"


def _configure_claude_mcp(*, force: bool) -> str:
    """Register the MCP server in ``~/.claude.json`` (user scope).

    Claude Code stores user-scope MCP servers at the top-level
    ``mcpServers`` key in ``~/.claude.json``.  The format matches
    the project-scoped ``.mcp.json`` structure.
    """
    data: dict[str, Any] = {}
    if _CLAUDE_JSON.exists():
        try:
            data = json.loads(_CLAUDE_JSON.read_text())
        except json.JSONDecodeError:
            data = {}

    servers: dict[str, Any] = data.setdefault("mcpServers", {})

    if _MCP_SERVER_NAME in servers and not force:
        return (
            f"SKIP   Claude Code MCP  '{_MCP_SERVER_NAME}' already in {_CLAUDE_JSON}"
            "  (use --force to overwrite)"
        )

    servers[_MCP_SERVER_NAME] = {
        "type": "stdio",
        "command": _MCP_COMMAND,
        "args": _MCP_ARGS,
    }
    _CLAUDE_JSON.write_text(json.dumps(data, indent=2) + "\n")
    return f"MCP    Claude Code: '{_MCP_SERVER_NAME}' → {_CLAUDE_JSON}"


# ---------------------------------------------------------------------------
# MCP configuration helpers — GitHub Copilot CLI (~/.copilot/mcp-config.json)
# ---------------------------------------------------------------------------

_COPILOT_MCP_JSON = Path.home() / ".copilot" / "mcp-config.json"


def _configure_copilot_mcp(*, force: bool) -> str:
    """Register the MCP server in ``~/.copilot/mcp-config.json``."""
    data: dict[str, Any] = {"mcpServers": {}}
    if _COPILOT_MCP_JSON.exists():
        try:
            data = json.loads(_COPILOT_MCP_JSON.read_text())
        except json.JSONDecodeError:
            data = {"mcpServers": {}}
    data.setdefault("mcpServers", {})

    if _MCP_SERVER_NAME in data["mcpServers"] and not force:
        return (
            f"SKIP   Copilot CLI MCP  '{_MCP_SERVER_NAME}' already in"
            f" {_COPILOT_MCP_JSON}  (use --force to overwrite)"
        )

    data["mcpServers"][_MCP_SERVER_NAME] = {
        "type": "stdio",
        "command": _MCP_COMMAND,
        "args": _MCP_ARGS,
    }
    _COPILOT_MCP_JSON.parent.mkdir(parents=True, exist_ok=True)
    _COPILOT_MCP_JSON.write_text(json.dumps(data, indent=2) + "\n")
    return f"MCP    Copilot CLI: '{_MCP_SERVER_NAME}' → {_COPILOT_MCP_JSON}"


# ---------------------------------------------------------------------------
# MCP configuration helpers — Codex CLI (~/.codex/config.toml)
# ---------------------------------------------------------------------------

_CODEX_CONFIG_TOML = Path.home() / ".codex" / "config.toml"


def _configure_codex_mcp(*, force: bool) -> str:
    """Register the MCP server in ``~/.codex/config.toml``.

    Codex CLI uses TOML for configuration.  The MCP server block is:

    .. code-block:: toml

       [mcp_servers.llm-sca-tooling]
       command = "llm-sca-tooling"
       args = ["mcp", "serve"]

    We use a simple line-based approach to avoid requiring a TOML library
    as a hard dependency (``tomllib`` is stdlib in Python 3.11+ but we
    only require 3.12, so it's available).
    """
    import tomllib  # stdlib ≥ 3.11  # noqa: PLC0415

    existing: dict[str, Any] = {}
    if _CODEX_CONFIG_TOML.exists():
        try:
            existing = tomllib.loads(_CODEX_CONFIG_TOML.read_text())
        except Exception:  # noqa: BLE001
            existing = {}

    mcp_key = f"mcp_servers.{_MCP_SERVER_NAME}"
    servers: dict[str, Any] = existing.get("mcp_servers", {})
    if _MCP_SERVER_NAME in servers and not force:
        return (
            f"SKIP   Codex CLI MCP  '{_MCP_SERVER_NAME}' already in"
            f" {_CODEX_CONFIG_TOML}  (use --force to overwrite)"
        )

    # Append (or replace) the block using raw text so we don't disturb
    # the rest of the user's config.toml.
    config_text = _CODEX_CONFIG_TOML.read_text() if _CODEX_CONFIG_TOML.exists() else ""

    # Remove any existing block for this server.
    block_header = f"[{mcp_key}]"
    lines = config_text.splitlines(keepends=True)
    new_lines: list[str] = []
    skip = False
    for line in lines:
        stripped = line.strip()
        if stripped == block_header:
            skip = True
            continue
        if skip and stripped.startswith("["):
            skip = False
        if not skip:
            new_lines.append(line)

    # Build the new block.
    args_toml = "[" + ", ".join(f'"{a}"' for a in _MCP_ARGS) + "]"
    block = f"\n[{mcp_key}]\n" f'command = "{_MCP_COMMAND}"\n' f"args = {args_toml}\n"

    new_text = "".join(new_lines).rstrip("\n") + block
    _CODEX_CONFIG_TOML.parent.mkdir(parents=True, exist_ok=True)
    _CODEX_CONFIG_TOML.write_text(new_text)
    return f"MCP    Codex CLI: '{_MCP_SERVER_NAME}' → {_CODEX_CONFIG_TOML}"


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


def run(
    skill_roots: list[Path] = typer.Option(  # noqa: B006
        [],
        "--skill-root",
        "-s",
        help=(
            "Extra skill root to install into (repeatable). "
            "Defaults to ~/.claude/skills, ~/.copilot/skills, ~/.codex/skills "
            "whose parent directory already exists."
        ),
    ),
    no_mcp: bool = typer.Option(
        False,
        "--no-mcp",
        help="Skip MCP server configuration (only install skills).",
    ),
    symlink: bool = typer.Option(
        False,
        "--symlink",
        help="Symlink skill directories instead of copying (useful for development).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing skill directories and MCP server entries.",
    ),
    list_only: bool = typer.Option(
        False,
        "--list",
        help="Print what would be installed/configured and exit without writing.",
    ),
) -> None:
    """Install skills, sub-agents, and configure the MCP server for all AI agents.

    Installs the bundled llm-sca-tooling skills and sub-agent definition files
    into the skill and agents directories for Claude Code, GitHub Copilot CLI,
    and Codex CLI, then registers the MCP server in each agent's configuration.

    \b
    Skills installed    : ~/.claude/skills/<skill>/
                          ~/.copilot/skills/<skill>/
                          ~/.codex/skills/<skill>/
    Agents installed    : ~/.claude/agents/<skill>.md       (Claude Code)
                          ~/.copilot/agents/<skill>.agent.md (Copilot CLI)
    MCP registered in   : ~/.claude.json     (Claude Code user-scope)
                          ~/.copilot/mcp-config.json  (Copilot CLI)
                          ~/.codex/config.toml        (Codex CLI)
    """
    # Resolve skill roots: use explicit roots first, then defaults.
    resolved_skill_roots: list[Path]
    if skill_roots:
        resolved_skill_roots = [p.expanduser().resolve() for p in skill_roots]
    else:
        resolved_skill_roots = [
            root for root in _SKILL_ROOTS.values() if root.parent.is_dir()
        ]
        if not resolved_skill_roots:
            # Fallback: Claude Code root even if ~/.claude/skills doesn't exist yet.
            resolved_skill_roots = [_SKILL_ROOTS["claude"]]

    if list_only:
        data_root = skill_data_root()
        typer.echo(f"skill_data : {data_root}")
        for skill_name in SKILL_NAMES:
            for root in resolved_skill_roots:
                typer.echo(f"  skill    : {root / skill_name}")
            typer.echo(
                f"  agent    : {_CLAUDE_AGENTS_DIR / skill_name}.md  (Claude Code)"
            )
            typer.echo(
                f"  agent    : {_COPILOT_AGENTS_DIR / skill_name}.agent.md"
                "  (Copilot CLI)"
            )
        if not no_mcp:
            typer.echo(f"  mcp      : {_CLAUDE_JSON}  (Claude Code)")
            typer.echo(f"  mcp      : {_COPILOT_MCP_JSON}  (Copilot CLI)")
            typer.echo(f"  mcp      : {_CODEX_CONFIG_TOML}  (Codex CLI)")
        return

    # --- Install skills ---
    typer.echo("Installing skills …")
    for msg in _install_skills(resolved_skill_roots, symlink=symlink, force=force):
        typer.echo(f"  {msg}")

    # --- Install agent definition files ---
    typer.echo("Installing agent definition files …")
    for msg in _install_claude_agents(force=force):
        typer.echo(f"  {msg}")
    for msg in _install_copilot_agents(force=force):
        typer.echo(f"  {msg}")

    # --- Configure MCP servers ---
    if not no_mcp:
        typer.echo("Configuring MCP servers …")
        for configure_fn in (
            _configure_claude_mcp,
            _configure_copilot_mcp,
            _configure_codex_mcp,
        ):
            try:
                msg = configure_fn(force=force)
                typer.echo(f"  {msg}")
            except Exception as exc:  # noqa: BLE001
                typer.echo(f"  WARN   {configure_fn.__name__}: {exc}", err=True)

    typer.echo("")
    typer.echo(
        "[green]Setup complete.[/green] "
        "Restart your agent to load the new skills and MCP server."
        if False  # rich markup only works in rich context; keep it plain
        else "Setup complete. Restart your agent to load the new skills and MCP server."
    )
