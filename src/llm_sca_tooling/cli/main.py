"""Phase 0 Typer/Rich command-line entrypoint."""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import orjson
import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from llm_sca_tooling import __version__
from llm_sca_tooling.config import Config, load_config, redacted_config
from llm_sca_tooling.errors import ConfigError, LLMSCAError

app = typer.Typer(name="llm-sca-tooling", no_args_is_help=True)
config_app = typer.Typer(no_args_is_help=True)
harness_app = typer.Typer(no_args_is_help=True)
run_app = typer.Typer(no_args_is_help=True)
mcp_app = typer.Typer(no_args_is_help=True)
console = Console(force_terminal=False)

app.add_typer(config_app, name="config")
app.add_typer(harness_app, name="harness")
app.add_typer(run_app, name="run")
app.add_typer(mcp_app, name="mcp")


@app.callback(invoke_without_command=True)
def app_callback(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Print package version and exit.",
            is_eager=True,
        ),
    ] = False,
    log_level: Annotated[
        str,
        typer.Option("--log-level", help="Root log level for CLI commands."),
    ] = "INFO",
) -> None:
    """LLM-augmented static code analysis tooling."""

    _setup_logging(log_level)
    if version:
        console.print(f"llm-sca-tooling {__version__}")
        raise typer.Exit(code=0)
    if ctx.invoked_subcommand is None:
        return


@app.command("version")
def version_command() -> None:
    """Print package and runtime versions."""

    table = Table(show_header=False)
    table.add_column("Component")
    table.add_column("Version")
    table.add_row("llm-sca-tooling", __version__)
    table.add_row("python", platform.python_version())
    table.add_row("uv", _uv_version())
    console.print(table)


@config_app.command("show")
def config_show(
    config_path: Annotated[
        Path | None,
        typer.Option("--path", exists=True, dir_okay=False, resolve_path=True),
    ] = None,
) -> None:
    """Print the active configuration with sensitive fields redacted."""

    loaded = _load_or_exit(config_path)
    table = Table(title="Configuration")
    table.add_column("Key")
    table.add_column("Value")
    for key, value in _flatten(redacted_config(loaded)).items():
        table.add_row(key, _json_text(value))
    console.print(table)


@config_app.command("validate")
def config_validate(
    config_path: Annotated[
        Path | None,
        typer.Option("--path", exists=True, dir_okay=False, resolve_path=True),
    ] = None,
) -> None:
    """Validate the active configuration."""

    _load_or_exit(config_path)
    console.print("configuration valid")


@harness_app.command("status")
def harness_status() -> None:
    """Print the harness stage, readiness score, and active permission profile."""

    config_obj = load_config()
    stage_path = Path(".agent/harness-stage.json")
    readiness_path = Path(".agent/eval/readiness.md")
    stage = _read_stage_record(stage_path)
    readiness = _read_readiness_machine_block(readiness_path)

    table = Table(title="Harness Status")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("stage", str(stage.get("stage", readiness.get("stage", "unknown"))))
    table.add_row(
        "total",
        str(
            stage.get("readiness_score", {}).get(
                "total", readiness.get("total", "unknown")
            )
        ),
    )
    table.add_row("agent_config", str(_axis_score(stage, readiness, "agent_config")))
    table.add_row("documentation", str(_axis_score(stage, readiness, "documentation")))
    table.add_row("cicd", str(_axis_score(stage, readiness, "cicd", "ci_cd")))
    table.add_row(
        "code_structure", str(_axis_score(stage, readiness, "code_structure"))
    )
    table.add_row("security", str(_axis_score(stage, readiness, "security")))
    table.add_row("permission_profile", config_obj.policy.permission_profile)
    console.print(table)


@run_app.command("create")
def run_create(
    workflow: Annotated[str, typer.Argument(help="Workflow name for the run.")],
    run_dir: Annotated[
        Path,
        typer.Option("--run-dir", file_okay=False, resolve_path=True),
    ] = Path(".agent/runs"),
) -> None:
    """Create a dummy file-backed run record."""

    from llm_sca_tooling.operations.run_records import RunRecordWriter

    writer = RunRecordWriter(run_dir)
    config_obj = load_config()
    run_id = writer.create_run(
        workflow=workflow,
        repos=[],
        model_backend="none",
        policy_id="phase0-default",
        permission_profile=config_obj.policy.permission_profile,
        context_budget=config_obj.budget.max_tokens,
        redaction_policy="redacted",
    )
    console.print(run_id)


@mcp_app.command("start")
def mcp_start(
    workspace: Annotated[
        Path,
        typer.Option("--workspace", file_okay=False, resolve_path=True),
    ] = Path(".llm-sca"),
) -> None:
    """Start the local MCP facade in development mode long enough to smoke test it."""

    from llm_sca_tooling.mcp_server.config import McpServerConfig
    from llm_sca_tooling.mcp_server.server import CodeIntelligenceServer

    server = CodeIntelligenceServer(McpServerConfig.for_workspace(workspace)).start()
    try:
        console.print(_json_text(server.health_check()))
    finally:
        server.shutdown()


def main(argv: list[str] | None = None) -> int:
    """Compatibility wrapper for programmatic CLI invocation."""

    try:
        app(args=argv, prog_name="llm-sca-tooling")
        return 0
    except ConfigError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1
    except LLMSCAError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        logging.getLogger(__name__).error("Unhandled CLI error: %s", exc, exc_info=True)
        console.print("[red]Error:[/red] unexpected failure")
        return 2


def _setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if root.handlers:
        return
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )


def _load_or_exit(path: Path | None) -> Config:
    try:
        return load_config(path)
    except ConfigError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


def _read_stage_record(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = orjson.loads(path.read_bytes())
    except orjson.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _read_readiness_machine_block(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    in_block = False
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "```":
            in_block = not in_block
            continue
        if in_block and "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def _axis_score(
    stage: dict[str, object],
    readiness: dict[str, str],
    key: str,
    fallback_key: str | None = None,
) -> object:
    scores = stage.get("readiness_score", {})
    if isinstance(scores, dict):
        if key in scores:
            return scores[key]
        if fallback_key and fallback_key in scores:
            return scores[fallback_key]
    return readiness.get(key, readiness.get(fallback_key or "", "unknown"))


def _flatten(value: object, prefix: str = "") -> dict[str, object]:
    if isinstance(value, dict):
        rows: dict[str, object] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            rows.update(_flatten(child, child_prefix))
        return rows
    return {prefix: value}


def _json_text(value: object) -> str:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS).decode("utf-8")


def _uv_version() -> str:
    uv_path = shutil.which("uv")
    if uv_path is None:
        return "unknown"
    try:
        completed = subprocess.run(  # noqa: S603 - `uv_path` comes from shutil.which.
            [uv_path, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


if __name__ == "__main__":
    sys.exit(main())
