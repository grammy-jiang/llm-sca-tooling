"""``llm-sca-tooling setup`` — detect AI agents and install skills/agents/MCP.

Detects which AI coding agents are installed on the system, then installs the
bundled skills and sub-agent definition files and registers the
``llm-sca-tooling`` MCP server only for the detected agents.

Detected agents and their configuration
-----------------------------------------
Claude Code (``claude`` binary)
  * Skills    → ``~/.claude/skills/<name>/``       (Claude-specific path)
  * Subagents → ``~/.claude/agents/<name>.md``     (YAML frontmatter + body)
  * MCP       → ``~/.claude.json``                 (user-scope ``mcpServers``)

GitHub Copilot CLI (``gh copilot`` extension)
  * Skills    → ``~/.agents/skills/<name>/``       (Agent Skills standard, user-level)
  * Subagents → ``~/.copilot/agents/<name>.agent.md``
  * MCP       → ``~/.copilot/mcp-config.json``

Codex CLI (``codex`` binary)
  * Skills    → ``~/.agents/skills/<name>/``       (Agent Skills standard, user-level)
  * MCP only  → ``~/.codex/config.toml``           (``[mcp_servers.*]`` section)
  * (Codex has no separate sub-agent directory; skill UI metadata goes in
    ``agents/openai.yaml`` inside each skill directory — see Codex skills docs)

Note: Both GitHub Copilot CLI and Codex CLI use the Agent Skills open standard
(https://agentskills.io) for user-level skills, so they share the same
``~/.agents/skills/`` directory.  Skills are installed once to that shared
location and both agents discover them automatically.

Detection logic
---------------
* Claude Code  : ``shutil.which("claude")``
* Copilot CLI  : ``shutil.which("gh")`` and ``gh copilot --version`` exits 0
* Codex CLI    : ``shutil.which("codex")``

Pass ``--all`` to install for all agents regardless of detection (useful in
CI or when an agent is installed but its binary is not on PATH).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# Agent detection
# ---------------------------------------------------------------------------


def _detect_claude() -> tuple[bool, str]:
    """Return (found, reason) for Claude Code."""
    path = shutil.which("claude")
    if path:
        return True, f"found {path}"
    return False, "'claude' not on PATH"


def _detect_copilot() -> tuple[bool, str]:
    """Return (found, reason) for GitHub Copilot CLI (gh copilot extension)."""
    gh = shutil.which("gh")
    if not gh:
        return False, "'gh' not on PATH"
    try:
        result = subprocess.run(  # noqa: S603  # gh is full path from shutil.which
            [gh, "copilot", "--version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            ver = result.stdout.decode(errors="replace").strip().splitlines()[0]
            return True, f"gh copilot — {ver}"
        return False, "'gh copilot' returned non-zero exit code"
    except Exception as exc:  # noqa: BLE001
        return False, f"gh copilot probe failed: {exc}"


def _detect_codex() -> tuple[bool, str]:
    """Return (found, reason) for Codex CLI."""
    path = shutil.which("codex")
    if path:
        return True, f"found {path}"
    return False, "'codex' not on PATH"


# ---------------------------------------------------------------------------
# Per-agent configuration descriptors
# ---------------------------------------------------------------------------


@dataclass
class _AgentConfig:
    """Encapsulates all installable artefacts for one AI agent."""

    display: str  # Human-readable name
    skill_root: Path | None  # None → agent has no skills directory
    agents_dir: Path | None  # None → agent has no sub-agent directory
    agents_suffix: str  # File extension suffix for sub-agent files ("" or ".agent")
    configure_mcp: Callable[..., str]  # fn(force=bool) → status message
    extra_msgs: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Skill installation helpers
# ---------------------------------------------------------------------------


# Files/dirs in the skill source tree that are NOT part of the skill itself
# and must be excluded when copying to agents' skill directories.
# - agent.md    → goes to ~/.claude/agents/ and ~/.copilot/agents/ separately
# - agents/     → Codex-specific UI metadata (agents/openai.yaml); only
#                 relevant for ~/.agents/skills/ (Codex/Copilot path), where
#                 Codex reads agents/openai.yaml for UI config.  Claude Code
#                 doesn't need it and its presence may confuse skill scanning.
_SKILL_COPY_EXCLUDES: frozenset[str] = frozenset({"agent.md"})

# For Claude Code's skill dir specifically, also exclude the agents/ subdir
# (Codex UI metadata is irrelevant there and could cause confusion).
_SKILL_COPY_EXCLUDES_CLAUDE: frozenset[str] = _SKILL_COPY_EXCLUDES | {"agents"}


def _install_skill(
    src: Path,
    dst: Path,
    *,
    symlink: bool,
    force: bool,
    exclude: frozenset[str] = frozenset(),
) -> str:
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

    def _ignore(directory: str, contents: list[str]) -> list[str]:
        return [name for name in contents if name in exclude]

    shutil.copytree(src, dst, ignore=_ignore if exclude else None)
    return f"COPY   {dst}"


def _install_skills_into(
    root: Path,
    *,
    symlink: bool,
    force: bool,
    exclude: frozenset[str] = frozenset(),
) -> list[str]:
    """Install all bundled skills into *root*."""
    data_root = skill_data_root()
    msgs: list[str] = []
    for skill_name in SKILL_NAMES:
        src = data_root / skill_name
        dst = root / skill_name
        msgs.append(
            _install_skill(src, dst, symlink=symlink, force=force, exclude=exclude)
        )
    return msgs


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


def _install_agents_into(agents_dir: Path, suffix: str, *, force: bool) -> list[str]:
    """Install agent definition files into *agents_dir*."""
    data_root = skill_data_root()
    msgs: list[str] = []
    for skill_name in SKILL_NAMES:
        src = data_root / skill_name / "agent.md"
        if not src.exists():
            msgs.append(f"WARN   {src} not found, skipping")
            continue
        dst = agents_dir / f"{skill_name}{suffix}.md"
        msgs.append(_install_agent_file(src, dst, force=force))
    return msgs


# ---------------------------------------------------------------------------
# MCP configuration helpers — Claude Code  (~/.claude.json, user scope)
# ---------------------------------------------------------------------------

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
# Agent registry  (ordered; detection runs in this order)
# ---------------------------------------------------------------------------

_AGENTS: dict[str, _AgentConfig] = {
    "claude": _AgentConfig(
        display="Claude Code",
        skill_root=Path.home() / ".claude" / "skills",
        agents_dir=Path.home() / ".claude" / "agents",
        agents_suffix="",  # ~/.claude/agents/<name>.md
        configure_mcp=_configure_claude_mcp,
    ),
    "copilot": _AgentConfig(
        display="GitHub Copilot CLI",
        # Copilot CLI follows the Agent Skills open standard — user-level skills
        # live at ~/.agents/skills/ (same location as Codex CLI).
        skill_root=Path.home() / ".agents" / "skills",
        agents_dir=Path.home() / ".copilot" / "agents",
        agents_suffix=".agent",  # ~/.copilot/agents/<name>.agent.md
        configure_mcp=_configure_copilot_mcp,
    ),
    "codex": _AgentConfig(
        display="Codex CLI",
        # Codex CLI uses the Agent Skills open standard — confirmed in official docs.
        # User-level skills live at ~/.agents/skills/ (shared with Copilot CLI).
        # If both Copilot and Codex are configured, skills are written once;
        # subsequent writes are no-ops unless --force is passed.
        skill_root=Path.home() / ".agents" / "skills",
        # Codex has no separate sub-agent directory — skill UI / invocation
        # policy is controlled via agents/openai.yaml inside each skill dir.
        agents_dir=None,
        agents_suffix="",
        configure_mcp=_configure_codex_mcp,
        extra_msgs=[
            "Codex sub-agent config lives in agents/openai.yaml within each skill dir."
        ],
    ),
}

_DETECTORS: dict[str, Callable[[], tuple[bool, str]]] = {
    "claude": _detect_claude,
    "copilot": _detect_copilot,
    "codex": _detect_codex,
}


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


def run(
    no_mcp: bool = typer.Option(
        False,
        "--no-mcp",
        help="Skip MCP server configuration (only install skills and agents).",
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
        help="Overwrite existing skill directories, agent files, and MCP entries.",
    ),
    all_agents: bool = typer.Option(
        False,
        "--all",
        help=(
            "Install for all agents regardless of detection. "
            "Useful when an agent binary is not on PATH."
        ),
    ),
    list_only: bool = typer.Option(
        False,
        "--list",
        help="Print detected agents and what would be installed, then exit.",
    ),
) -> None:
    """Detect AI agents and install skills, sub-agents, and MCP configuration.

    Detects which AI coding agents (Claude Code, GitHub Copilot CLI, Codex CLI)
    are installed, then installs the bundled skills and sub-agent definition
    files and registers the MCP server only for the detected agents.

    \b
    Claude Code (claude binary)
      Skills    : ~/.claude/skills/<skill>/
      Subagents : ~/.claude/agents/<skill>.md
      MCP       : ~/.claude.json

    GitHub Copilot CLI (gh copilot extension)
      Skills    : ~/.agents/skills/<skill>/   (Agent Skills standard)
      Subagents : ~/.copilot/agents/<skill>.agent.md
      MCP       : ~/.copilot/mcp-config.json

    Codex CLI (codex binary)
      Skills    : ~/.agents/skills/<skill>/   (Agent Skills standard, shared)
      MCP       : ~/.codex/config.toml

    Copilot CLI and Codex CLI share ~/.agents/skills/ — skills are installed
    once to that location and both agents discover them automatically.

    Use --all to install for all agents regardless of detection.
    """
    # ── Detection phase ───────────────────────────────────────────────────
    typer.echo("Detecting installed AI agents …")
    detected: dict[str, bool] = {}
    for key, detect_fn in _DETECTORS.items():
        found, reason = detect_fn()
        effective = found or all_agents
        detected[key] = effective
        status = "FOUND " if found else "MISS  "
        suffix = "  (will configure — --all)" if (all_agents and not found) else ""
        typer.echo(f"  {status} {_AGENTS[key].display}: {reason}{suffix}")

    active_keys = [k for k, v in detected.items() if v]
    if not active_keys:
        typer.echo("")
        typer.echo(
            "No supported AI agents detected. Install claude, gh copilot, or codex"
            " and re-run setup, or pass --all to configure regardless."
        )
        raise typer.Exit(1)

    typer.echo("")

    if list_only:
        data_root = skill_data_root()
        typer.echo(f"skill_data : {data_root}")
        for key in active_keys:
            cfg = _AGENTS[key]
            typer.echo(f"\n  [{cfg.display}]")
            if cfg.skill_root is not None:
                for sn in SKILL_NAMES:
                    typer.echo(f"    skill    : {cfg.skill_root / sn}")
            else:
                typer.echo("    skills   : (not supported)")
            if cfg.agents_dir is not None:
                for sn in SKILL_NAMES:
                    typer.echo(
                        f"    agent    : {cfg.agents_dir / sn}{cfg.agents_suffix}.md"
                    )
            else:
                typer.echo("    agents   : (not supported)")
            if not no_mcp:
                typer.echo(f"    mcp      : (via {cfg.configure_mcp.__name__})")
        return

    # ── Install phase ─────────────────────────────────────────────────────
    for key in active_keys:
        cfg = _AGENTS[key]
        typer.echo(f"Configuring {cfg.display} …")

        if cfg.skill_root is not None:
            # Claude Code's skill dir must not contain agent.md or agents/
            # (those are subagent/Codex metadata, not skill content).
            # For ~/.agents/skills/ (Codex/Copilot) we keep agents/openai.yaml
            # but still strip agent.md.
            skill_excludes = (
                _SKILL_COPY_EXCLUDES_CLAUDE if key == "claude" else _SKILL_COPY_EXCLUDES
            )
            for msg in _install_skills_into(
                cfg.skill_root, symlink=symlink, force=force, exclude=skill_excludes
            ):
                typer.echo(f"  {msg}")
        else:
            typer.echo("  (no skills directory — skipping)")

        if cfg.agents_dir is not None:
            for msg in _install_agents_into(
                cfg.agents_dir, cfg.agents_suffix, force=force
            ):
                typer.echo(f"  {msg}")
        else:
            typer.echo("  (no sub-agents directory — skipping)")

        if not no_mcp:
            try:
                msg = cfg.configure_mcp(force=force)
                typer.echo(f"  {msg}")
            except Exception as exc:  # noqa: BLE001
                typer.echo(f"  WARN   MCP config failed: {exc}", err=True)

        typer.echo("")

    typer.echo(
        "Setup complete. Restart each configured agent to load new skills and MCP."
    )
