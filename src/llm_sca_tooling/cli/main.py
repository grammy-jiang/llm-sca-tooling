"""CLI entrypoint for llm-sca-tooling.

RichHandler is configured here, before any module logs output.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from llm_sca_tooling import __version__

# ------------------------------------------------------------------
# Logging setup — must run before importing other package modules
# ------------------------------------------------------------------


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )


_setup_logging()

# ------------------------------------------------------------------
# Import other modules AFTER logging is configured
# ------------------------------------------------------------------

from llm_sca_tooling.config import load_config  # noqa: E402
from llm_sca_tooling.errors import ConfigError  # noqa: E402

# ------------------------------------------------------------------
# App definition
# ------------------------------------------------------------------

app = typer.Typer(
    name="llm-sca-tooling",
    no_args_is_help=True,
    rich_markup_mode="rich",
    help="LLM-augmented Static Code Analysis tooling.",
)
config_app = typer.Typer(help="Configuration commands.")
harness_app = typer.Typer(help="Harness status commands.")
run_app = typer.Typer(help="Run record commands.")
mcp_app = typer.Typer(help="MCP server commands.")

app.add_typer(config_app, name="config")
app.add_typer(harness_app, name="harness")
app.add_typer(run_app, name="run")
app.add_typer(mcp_app, name="mcp")

console = Console()
err_console = Console(stderr=True)

_logger = logging.getLogger(__name__)

# Phase 19 sub-apps — imported after app/console are defined
from llm_sca_tooling.cli import setup as _setup_mod  # noqa: E402
from llm_sca_tooling.cli.diagnose import diagnose_app  # noqa: E402
from llm_sca_tooling.cli.release import release_app  # noqa: E402
from llm_sca_tooling.cli.replay import replay_app  # noqa: E402

app.add_typer(replay_app, name="replay")
app.add_typer(diagnose_app, name="diagnose")
app.add_typer(release_app, name="release")
app.command("setup")(_setup_mod.run)

# ------------------------------------------------------------------
# Top-level callback
# ------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V", help="Show version and exit."
    ),
    log_level: str = typer.Option("INFO", "--log-level", "-l", help="Log level."),
) -> None:
    """LLM-SCA Tooling — CLI interface."""
    _setup_logging(log_level)
    if version:
        console.print(f"llm-sca-tooling {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@app.command("release-gate")
def release_gate(
    suite: str = typer.Option("all", "--suite", help="Suite: t1, t2, t3, t4, all."),
    calibration_required: bool = typer.Option(
        True,
        "--calibration-required/--no-calibration-required",
        help="Require calibration gates.",
    ),
    adversarial_required: bool = typer.Option(
        True,
        "--adversarial-required/--no-adversarial-required",
        help="Require adversarial checks.",
    ),
    memory_gate_required: bool = typer.Option(
        True,
        "--memory-gate-required/--no-memory-gate-required",
        help="Require memory ship gate.",
    ),
    operational_gate_required: bool = typer.Option(
        True,
        "--operational-gate-required/--no-operational-gate-required",
        help="Require operational harness gates.",
    ),
    report_out: Path | None = typer.Option(
        None, "--report-out", help="Write machine-readable JSON report."
    ),
    fail_on_any: bool = typer.Option(
        False, "--fail-on-any", help="Fail when any enabled gate fails."
    ),
) -> None:
    """Run the Phase 18 release gate against the in-repo fixtures.

    Invokes ``run_release_gate`` which executes T3 / T4 runners,
    computes a real ``CalibrationReport`` from the runner outputs, and
    feeds the result into ``ReleaseGateEvaluator``.  Replaces the
    earlier fixture-builder path that fabricated passing inputs.
    """
    from llm_sca_tooling.release.release_gate import (  # noqa: PLC0415
        run_release_gate,
        write_release_gate_report,
    )

    try:
        result = run_release_gate(
            suite=suite,
            calibration_required=calibration_required,
            adversarial_required=adversarial_required,
            memory_gate_required=memory_gate_required,
            operational_gate_required=operational_gate_required,
            fail_on_any=fail_on_any,
        )
    except ValueError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    if report_out is not None:
        write_release_gate_report(result, report_out)
    table = Table(title="Release Gate", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value")
    table.add_row("Overall pass", str(result.overall_pass))
    table.add_row(
        "Suites", ", ".join(item.suite_id for item in result.benchmark_results)
    )
    table.add_row("Disabled gates", ", ".join(result.disabled_gates) or "none")
    table.add_row("Failing gates", ", ".join(result.failing_gates) or "none")
    console.print(table)
    if not result.overall_pass:
        raise typer.Exit(code=1)


# ------------------------------------------------------------------
# config sub-commands
# ------------------------------------------------------------------


@config_app.command("show")
def config_show(
    config_file: Path | None = typer.Option(  # noqa: B008
        None, "--config", "-c", help="Config file path."
    ),
) -> None:
    """Print the current configuration with sensitive fields redacted."""
    try:
        cfg = load_config(config_file)
    except ConfigError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title="Configuration", show_header=True)
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    def _flatten(d: object, prefix: str = "") -> list[tuple[str, str]]:
        if not isinstance(d, dict):
            return [(prefix.rstrip("."), str(d))]
        rows: list[tuple[str, str]] = []
        for k, v in d.items():
            rows.extend(_flatten(v, f"{prefix}{k}."))
        return rows

    for key, value in _flatten(cfg.redacted()):
        table.add_row(key, value)
    console.print(table)


@config_app.command("validate")
def config_validate(
    config_file: Path | None = typer.Argument(
        None, help="Config file path."
    ),  # noqa: B008
) -> None:
    """Validate the configuration and exit 0 on success, 1 on error."""
    try:
        load_config(config_file)
        console.print("[green]Configuration is valid.[/green]")
    except ConfigError as exc:
        err_console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


# ------------------------------------------------------------------
# harness sub-commands
# ------------------------------------------------------------------


@harness_app.command("status")
def harness_status() -> None:
    """Print harness stage, per-axis readiness score, and active permission profile."""
    try:
        import subprocess  # noqa: S603,PLC0415

        result = subprocess.run(  # noqa: S603
            ["local-agent-harness", "assess", "--repo", ".", "--json"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            import json  # noqa: PLC0415

            data = json.loads(result.stdout)
            table = Table(title="Harness Status", show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value")
            table.add_row("Stage", data.get("stage", "unknown"))
            table.add_row("Total score", str(data.get("total", "?")))
            for axis, score in data.get("axes", {}).items():
                table.add_row(f"  {axis}", str(score))
            console.print(table)
        else:
            err_console.print(
                "[yellow]Warning:[/yellow] local-agent-harness not available."
            )
    except Exception as exc:  # noqa: BLE001
        _logger.error("harness status failed: %s", exc, exc_info=True)
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=2) from exc


# ------------------------------------------------------------------
# run sub-commands
# ------------------------------------------------------------------


@run_app.command("create")
def run_create(workflow: str = typer.Argument(..., help="Workflow name.")) -> None:
    """Create a dummy run record (for testing)."""
    import asyncio  # noqa: PLC0415

    from llm_sca_tooling.operations.run_records import RunRecordWriter  # noqa: PLC0415

    async def _run() -> None:
        writer = RunRecordWriter()
        run_id = await writer.create_run(workflow, repos=[])
        console.print(f"[green]Created run:[/green] {run_id}")

    try:
        asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        _logger.error("run create failed: %s", exc, exc_info=True)
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


# ------------------------------------------------------------------
# mcp sub-commands
# ------------------------------------------------------------------


@mcp_app.command("start")
def mcp_start(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(3000, help="Bind port."),
) -> None:
    """Start the MCP server in development mode."""
    from llm_sca_tooling.config import MCPConfig  # noqa: PLC0415
    from llm_sca_tooling.mcp_server.server import MCPServer  # noqa: PLC0415

    cfg = MCPConfig(host=host, port=port, dev_mode=True)
    server = MCPServer(cfg)
    console.print(f"Starting MCP server on [cyan]{host}:{port}[/cyan] (dev mode)")
    try:
        server.start()
    except KeyboardInterrupt:
        console.print("\n[yellow]MCP server stopped.[/yellow]")
    except Exception as exc:  # noqa: BLE001
        _logger.error("MCP server error: %s", exc, exc_info=True)
        raise typer.Exit(code=1) from exc


@mcp_app.command("serve")
def mcp_serve(
    transport: str = typer.Option(
        "stdio", "--transport", help="Transport mode: stdio or http."
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host (http mode)."),
    port: int = typer.Option(8080, "--port", help="Bind port (http mode)."),
    tls_enabled: bool = typer.Option(False, "--tls/--no-tls"),
    tls_cert: str | None = typer.Option(None, "--tls-cert"),
    tls_key: str | None = typer.Option(None, "--tls-key"),
    cors_origin: list[str] = typer.Option([], "--cors-origin"),  # noqa: B006
    auth_token_env: str | None = typer.Option(None, "--auth-token-env"),
) -> None:
    """Start the MCP server (stdio or streamable HTTP transport)."""
    if transport == "http":
        from llm_sca_tooling.transport.http_transport import (  # noqa: PLC0415
            HTTPTransportConfig,
            start_http_server,
        )

        cfg = HTTPTransportConfig(
            host=host,
            port=port,
            tls_enabled=tls_enabled,
            tls_cert_path=tls_cert,
            tls_key_path=tls_key,
            cors_allowed_origins=cors_origin,
            auth_token_env_var=auth_token_env,
        )
        violations = cfg.validate_security()
        if violations:
            for v in violations:
                err_console.print(f"[red]Security violation:[/red] {v}")
            raise typer.Exit(code=2)
        console.print(f"Starting MCP server (HTTP) on [cyan]{host}:{port}[/cyan]")
        from llm_sca_tooling.config import MCPConfig  # noqa: PLC0415
        from llm_sca_tooling.mcp_server.server import MCPServer  # noqa: PLC0415

        mcp_cfg = MCPConfig(host=host, port=port, dev_mode=False)
        server = MCPServer(mcp_cfg)
        try:
            start_http_server(cfg, server)
        except KeyboardInterrupt:
            console.print("\n[yellow]MCP server stopped.[/yellow]")
        except Exception as exc:  # noqa: BLE001
            _logger.error("MCP server error: %s", exc, exc_info=True)
            raise typer.Exit(code=1) from exc
    else:
        # stdio transport: ALL diagnostic output must go to stderr so that
        # stdout carries only JSON-RPC frames.  Never call console.print()
        # (which writes to stdout) from this path.
        from llm_sca_tooling.config import MCPConfig  # noqa: PLC0415
        from llm_sca_tooling.mcp_server.server import MCPServer  # noqa: PLC0415

        # Redirect all logging to stderr so stdout stays clean for JSON-RPC.
        _logging = __import__("logging")
        for handler in _logging.root.handlers[:]:
            _logging.root.removeHandler(handler)
        _logging.basicConfig(
            level=_logging.INFO,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[
                RichHandler(
                    rich_tracebacks=True,
                    show_path=False,
                    console=Console(stderr=True),
                )
            ],
            force=True,
        )

        stdio_console = Console(stderr=True)
        mcp_cfg = MCPConfig(host="127.0.0.1", port=8080, dev_mode=False)
        server = MCPServer(mcp_cfg)
        stdio_console.print(
            "[dim]MCP server (stdio) starting — JSON-RPC on stdin/stdout[/dim]"
        )
        try:
            server.start_stdio()
        except KeyboardInterrupt:
            stdio_console.print("[yellow]MCP server stopped.[/yellow]")
        except Exception as exc:  # noqa: BLE001
            _logger.error("MCP server error: %s", exc, exc_info=True)
            raise typer.Exit(code=1) from exc
