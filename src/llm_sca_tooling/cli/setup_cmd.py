"""Setup subcommand: detect local AI agents and configure MCP + skills."""

from __future__ import annotations

import logging
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import orjson
import tomli_w

from llm_sca_tooling.skill_templates.bundled import PRODUCT_SKILLS

logger = logging.getLogger(__name__)

_SERVER_NAME = "evidence-sca"
_MCP_COMMAND = "evidence-sca"
_MCP_ARGS = ["mcp", "serve"]

# Skills installed by this package live here (relative to any detected repo root).
_SKILLS_DIR = ".skills"
_AGENT_SKILLS_DIR = ".agent/skills"


@dataclass
class SetupResult:
    agent: str
    configured: bool
    skipped: bool = False
    detail: str = ""
    errors: list[str] = field(default_factory=list)


def _build_mcp_command(use_uv: bool, workspace: str) -> tuple[str, list[str]]:
    """Return (command, args) for the MCP server entry.

    Normal install:  evidence-sca mcp serve [--workspace ...]
    uv dev mode:     uv run evidence-sca mcp serve [--workspace ...]
    """
    base_args = list(_MCP_ARGS)
    if workspace != ".llm-sca":
        base_args += ["--workspace", workspace]
    if use_uv:
        return "uv", ["run", _MCP_COMMAND] + base_args
    return _MCP_COMMAND, base_args


def run_setup(
    workspace: str = ".llm-sca",
    dry_run: bool = False,
    use_uv: bool | None = None,
    install_skills: bool = True,
    repo_root: Path | None = None,
) -> list[SetupResult]:
    """Detect AI agents and configure MCP server + skills for each.

    Args:
        workspace: Workspace path argument passed to ``evidence-sca mcp serve``.
        dry_run: If *True* print what would change without writing.
        use_uv: If *True* wrap the server command as ``uv run evidence-sca ...``
            instead of calling the installed binary directly.  Use this when
            working inside a uv-managed source repository so the MCP server
            always runs the local editable install rather than the
            system-installed binary.  If *None*, this is auto-detected from the
            repository shape.
        install_skills: If *True*, install packaged product skill templates into
            ``.skills/`` without overwriting existing files.
        repo_root: Override the repository root (defaults to cwd).

    Returns:
        One ``SetupResult`` per detected agent.
    """
    root = repo_root or Path.cwd()
    resolved_use_uv = _is_source_checkout(root) if use_uv is None else use_uv
    command, mcp_args = _build_mcp_command(resolved_use_uv, workspace)
    if install_skills:
        _install_product_skills(root, dry_run)

    results: list[SetupResult] = []

    # Claude Code
    results.append(_setup_claude_code(root, command, mcp_args, dry_run))
    # GitHub Copilot
    results.append(_setup_copilot(root, command, mcp_args, dry_run))
    # OpenAI Codex CLI
    results.append(_setup_codex(root, command, mcp_args, dry_run))

    return results


# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------


def _setup_claude_code(
    root: Path, command: str, mcp_args: list[str], dry_run: bool
) -> SetupResult:
    """Configure .mcp.json for Claude Code (project scope)."""
    agent = "claude-code"
    if not _detect_claude_code():
        return SetupResult(
            agent=agent,
            configured=False,
            skipped=True,
            detail="claude binary not found",
        )

    mcp_json_path = root / ".mcp.json"
    config: dict[str, Any] = {}
    if mcp_json_path.exists():
        try:
            config = orjson.loads(mcp_json_path.read_bytes())
        except (ValueError, OSError) as exc:
            return SetupResult(
                agent=agent,
                configured=False,
                errors=[f"Could not read .mcp.json: {exc}"],
            )

    servers: dict[str, Any] = config.setdefault("mcpServers", {})
    if _SERVER_NAME in servers:
        return SetupResult(
            agent=agent,
            configured=False,
            skipped=True,
            detail=(
                f"{_SERVER_NAME} already present in .mcp.json; "
                f"{_skills_note_claude(root)}"
            ),
        )

    servers[_SERVER_NAME] = {"command": command, "args": mcp_args}
    detail = _write_json(mcp_json_path, config, dry_run)
    logger.info("Claude Code: wrote MCP entry to %s", mcp_json_path)

    skills_note = _skills_note_claude(root)
    return SetupResult(agent=agent, configured=True, detail=f"{detail}; {skills_note}")


def _detect_claude_code() -> bool:
    if shutil.which("claude"):
        return True
    claude_dir = Path.home() / ".claude"
    return claude_dir.is_dir()


def _skills_note_claude(root: Path) -> str:
    return _skills_note(root)


# ---------------------------------------------------------------------------
# GitHub Copilot
# ---------------------------------------------------------------------------


def _setup_copilot(
    root: Path, command: str, mcp_args: list[str], dry_run: bool
) -> SetupResult:
    """Configure .vscode/mcp.json for GitHub Copilot (project scope)."""
    agent = "github-copilot"
    if not _detect_copilot():
        return SetupResult(
            agent=agent,
            configured=False,
            skipped=True,
            detail="gh copilot not detected",
        )

    vscode_dir = root / ".vscode"
    mcp_json_path = vscode_dir / "mcp.json"
    config: dict[str, Any] = {}
    if mcp_json_path.exists():
        try:
            config = orjson.loads(mcp_json_path.read_bytes())
        except (ValueError, OSError) as exc:
            return SetupResult(
                agent=agent,
                configured=False,
                errors=[f"Could not read .vscode/mcp.json: {exc}"],
            )

    servers: dict[str, Any] = config.setdefault("servers", {})
    if _SERVER_NAME in servers:
        return SetupResult(
            agent=agent,
            configured=False,
            skipped=True,
            detail=(
                f"{_SERVER_NAME} already present in .vscode/mcp.json; "
                f"{_skills_note_mcp(root)}"
            ),
        )

    servers[_SERVER_NAME] = {"command": command, "args": mcp_args}
    if not dry_run:
        vscode_dir.mkdir(parents=True, exist_ok=True)
    detail = _write_json(mcp_json_path, config, dry_run)
    logger.info("GitHub Copilot: wrote MCP entry to %s", mcp_json_path)

    return SetupResult(
        agent=agent, configured=True, detail=f"{detail}; {_skills_note_mcp(root)}"
    )


def _detect_copilot() -> bool:
    if shutil.which("gh"):
        return True
    # VS Code Copilot extension directory
    vscode_ext = Path.home() / ".vscode" / "extensions"
    if vscode_ext.is_dir():
        return any(p.name.startswith("github.copilot") for p in vscode_ext.iterdir())
    return False


# ---------------------------------------------------------------------------
# OpenAI Codex CLI
# ---------------------------------------------------------------------------


def _setup_codex(
    root: Path, command: str, mcp_args: list[str], dry_run: bool
) -> SetupResult:
    """Configure .codex/config.toml for OpenAI Codex CLI (project scope)."""
    agent = "codex-cli"
    if not _detect_codex():
        return SetupResult(
            agent=agent, configured=False, skipped=True, detail="codex binary not found"
        )

    codex_dir = root / ".codex"
    config_path = codex_dir / "config.toml"
    config: dict[str, Any] = {}
    if config_path.exists():
        try:
            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            return SetupResult(
                agent=agent,
                configured=False,
                errors=[f"Could not read .codex/config.toml: {exc}"],
            )

    mcp_servers: dict[str, Any] = config.setdefault("mcp_servers", {})
    if _SERVER_NAME in mcp_servers:
        return SetupResult(
            agent=agent,
            configured=False,
            skipped=True,
            detail=(
                f"{_SERVER_NAME} already present in .codex/config.toml; "
                f"{_skills_note_codex(root)}"
            ),
        )

    mcp_servers[_SERVER_NAME] = {"command": command, "args": mcp_args}
    if not dry_run:
        codex_dir.mkdir(parents=True, exist_ok=True)
    detail = _write_toml(config_path, config, dry_run)
    logger.info("Codex CLI: wrote MCP entry to %s", config_path)

    skills_note = _skills_note_codex(root)
    return SetupResult(agent=agent, configured=True, detail=f"{detail}; {skills_note}")


def _detect_codex() -> bool:
    if shutil.which("codex"):
        return True
    codex_dir = Path.home() / ".codex"
    return codex_dir.is_dir()


def _skills_note_codex(root: Path) -> str:
    return _skills_note(root)


def _skills_note_mcp(root: Path) -> str:
    if (
        (root / _SKILLS_DIR).is_dir()
        or (root / _AGENT_SKILLS_DIR).is_dir()
        or _packaged_product_skill_names()
    ):
        return "skills exposed via MCP resources: code-intelligence://skills"
    return "no repository skill templates found"


def _skills_note(root: Path) -> str:
    notes = [_skills_note_mcp(root)]
    product_names = _product_skill_names(root)
    if product_names:
        notes.append(f"product templates in {_SKILLS_DIR}/: {', '.join(product_names)}")
    agent_names = _agent_skill_names(root)
    if agent_names:
        notes.append(
            f"agent harness templates in {_AGENT_SKILLS_DIR}/: {', '.join(agent_names)}"
        )
    return "; ".join(notes)


def _product_skill_names(root: Path) -> list[str]:
    skills_dir = root / _SKILLS_DIR
    workspace_names = (
        [
            f.stem.replace(".SKILL", "").replace("_", "-")
            for f in sorted(skills_dir.glob("*.SKILL.md"))
            if not f.name.startswith("_")
        ]
        if skills_dir.is_dir()
        else []
    )
    if workspace_names:
        return workspace_names
    return _packaged_product_skill_names()


def _agent_skill_names(root: Path) -> list[str]:
    agent_skills_dir = root / _AGENT_SKILLS_DIR
    if agent_skills_dir.is_dir():
        return [p.name for p in sorted(agent_skills_dir.iterdir()) if p.is_dir()]
    return []


def _packaged_product_skill_names() -> list[str]:
    return [
        name.removesuffix(".SKILL.md").replace("_", "-")
        for name in sorted(PRODUCT_SKILLS)
        if name.endswith(".SKILL.md") and not name.startswith("_")
    ]


def _install_product_skills(root: Path, dry_run: bool) -> str:
    skills_dir = root / _SKILLS_DIR
    copied = 0
    existing = 0
    if not dry_run:
        skills_dir.mkdir(parents=True, exist_ok=True)
    for name, content in sorted(PRODUCT_SKILLS.items()):
        if not name.endswith(".SKILL.md") or name.startswith("_"):
            continue
        target = skills_dir / name
        if target.exists():
            existing += 1
            continue
        copied += 1
        if not dry_run:
            target.write_text(content, encoding="utf-8")
    action = "would install" if dry_run else "installed"
    return f"{action} {copied} product skill templates; {existing} already present"


def _is_source_checkout(root: Path) -> bool:
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file() or not (root / "src" / "llm_sca_tooling").is_dir():
        return False
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False
    project = data.get("project")
    return isinstance(project, dict) and project.get("name") == "llm-sca-tooling"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict[str, Any], dry_run: bool) -> str:
    content = orjson.dumps(data, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
    if dry_run:
        return f"[dry-run] would write {path}"
    path.write_bytes(content + b"\n")
    return f"wrote {path}"


def _write_toml(path: Path, data: dict[str, Any], dry_run: bool) -> str:
    content = tomli_w.dumps(data)
    if dry_run:
        return f"[dry-run] would write {path}"
    path.write_text(content, encoding="utf-8")
    return f"wrote {path}"


def print_results(results: list[SetupResult], *, verbose: bool = False) -> None:
    """Print setup results to stdout."""
    for r in results:
        status = "CONFIGURED" if r.configured else ("SKIPPED" if r.skipped else "ERROR")
        print(f"[{status}] {r.agent}: {r.detail or ''}")
        for err in r.errors:
            print(f"  ERROR: {err}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """CLI entry for 'evidence-sca setup'."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="evidence-sca setup",
        description=(
            "Detect local AI agents (Claude Code, GitHub Copilot, Codex CLI) "
            "and configure the evidence-sca MCP server and skills for each."
        ),
    )
    parser.add_argument(
        "--workspace",
        default=".llm-sca",
        help="evidence-sca workspace path (passed to 'evidence-sca mcp serve'). Default: .llm-sca",
    )
    runtime = parser.add_mutually_exclusive_group()
    runtime.add_argument(
        "--uv",
        action="store_true",
        dest="use_uv",
        help=(
            "Use 'uv run evidence-sca mcp serve' instead of the installed binary. "
            "Use this when developing inside the evidence-sca source repo itself."
        ),
    )
    runtime.add_argument(
        "--no-uv",
        action="store_false",
        dest="use_uv",
        help="Use the installed evidence-sca binary even inside a source checkout.",
    )
    parser.set_defaults(use_uv=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be configured without writing any files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show additional detail for each agent.",
    )
    args = parser.parse_args(argv)

    results = run_setup(
        workspace=args.workspace, dry_run=args.dry_run, use_uv=args.use_uv
    )
    print_results(results, verbose=args.verbose)

    any_error = any(r.errors for r in results)
    return 1 if any_error else 0
