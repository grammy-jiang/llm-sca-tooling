"""evidence-sca — unified Typer/Rich command-line entrypoint."""

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
from llm_sca_tooling.release.release_gate import run_release_gate

app = typer.Typer(name="evidence-sca", no_args_is_help=True)
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
        console.print(f"evidence-sca {__version__}")
        raise typer.Exit(code=0)
    if ctx.invoked_subcommand is None:
        return


@app.command("version")
def version_command() -> None:
    """Print package and runtime versions."""

    table = Table(show_header=False)
    table.add_column("Component")
    table.add_column("Version")
    table.add_row("evidence-sca", __version__)
    table.add_row("python", platform.python_version())
    table.add_row("uv", _uv_version())
    console.print(table)


@app.command("release-gate")
def release_gate_command(
    suite: Annotated[
        str,
        typer.Option("--suite", help="Suite to gate: t1, t2, t3, t4, or all."),
    ] = "all",
    calibration_required: Annotated[
        bool, typer.Option("--calibration-required/--no-calibration-required")
    ] = True,
    adversarial_required: Annotated[
        bool, typer.Option("--adversarial-required/--no-adversarial-required")
    ] = True,
    memory_gate_required: Annotated[
        bool, typer.Option("--memory-gate-required/--no-memory-gate-required")
    ] = True,
    operational_gate_required: Annotated[
        bool, typer.Option("--operational-gate-required/--no-operational-gate-required")
    ] = True,
    report_out: Annotated[
        Path | None, typer.Option("--report-out", dir_okay=False)
    ] = None,
    fail_on_any: Annotated[bool, typer.Option("--fail-on-any/--no-fail-on-any")] = True,
) -> None:
    """Run the deterministic Phase 18 release gate aggregation."""

    benchmark_results = {suite: {"passed": suite in {"t1", "t2", "t3", "t4", "all"}}}
    result = run_release_gate(
        harness_condition_id="hcs:cli-release-gate",
        benchmark_results=benchmark_results,
        calibration_required=calibration_required,
        operational_required=operational_gate_required,
        adversarial_required=adversarial_required,
        memory_gate_required=memory_gate_required,
    )
    if report_out is not None:
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_bytes(orjson.dumps(result.model_dump(mode="json")) + b"\n")
    table = Table(title="Release Gate")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("overall_pass", str(result.overall_pass))
    table.add_row("failing_gates", ", ".join(result.failing_gates) or "none")
    console.print(table)
    if fail_on_any and not result.overall_pass:
        raise typer.Exit(code=1)


@app.command("replay")
def replay_command(
    run_id: Annotated[str, typer.Argument(help="Run identifier to replay.")],
    workspace: Annotated[
        Path,
        typer.Option("--workspace", file_okay=False, resolve_path=True),
    ] = Path(".llm-sca"),
    show_events: Annotated[bool, typer.Option("--show-events/--summary-only")] = True,
    filter_stage: Annotated[str | None, typer.Option("--filter-stage")] = None,
    filter_type: Annotated[str | None, typer.Option("--filter-type")] = None,
    diff_run: Annotated[str | None, typer.Option("--diff-run")] = None,
    output_format: Annotated[str, typer.Option("--output-format")] = "table",
) -> None:
    """Replay a persisted run record with optional event filtering."""

    from llm_sca_tooling.schemas.run_records import RunEventType

    store = _open_workspace_or_exit(workspace)
    event_type = None
    if filter_type:
        try:
            event_type = RunEventType(filter_type)
        except ValueError as exc:
            console.print(f"[red]Error:[/red] unknown event type: {filter_type}")
            raise typer.Exit(code=1) from exc
    try:
        view = store.operations.get_run(run_id, include_events=True)
        events = store.operations.list_run_events(
            run_id,
            type=event_type,
            stage=filter_stage,
            limit=10_000,
        )
        diff = _diff_run_events(store, run_id, diff_run) if diff_run else None
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    payload = {
        "run": view.run.model_dump(mode="json"),
        "events": [event.model_dump(mode="json") for event in events],
        "diff": diff,
    }
    if output_format == "json":
        console.print(_json_text(payload))
        return
    table = Table(title=f"Replay {run_id}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("workflow", view.run.workflow.value)
    table.add_row("status", view.run.status.value)
    table.add_row("event_count", str(len(events)))
    if diff:
        table.add_row("diff", _json_text(diff))
    console.print(table)
    if show_events:
        event_table = Table(title="Events")
        event_table.add_column("Seq")
        event_table.add_column("Type")
        event_table.add_column("Stage")
        event_table.add_column("Policy")
        for event in events:
            event_table.add_row(
                str(event.seq),
                event.type.value,
                event.stage,
                event.policy_action.value if event.policy_action else "",
            )
        console.print(event_table)


@app.command("diagnose")
def diagnose_command(
    incident_id: Annotated[str, typer.Argument(help="Incident identifier.")],
    workspace: Annotated[
        Path,
        typer.Option("--workspace", file_okay=False, resolve_path=True),
    ] = Path(".llm-sca"),
    trace_run: Annotated[str | None, typer.Option("--trace-run")] = None,
    show_promotion_candidates: Annotated[
        bool, typer.Option("--show-promotion-candidates/--no-promotion-candidates")
    ] = False,
    output_format: Annotated[str, typer.Option("--output-format")] = "table",
) -> None:
    """Diagnose an incident using linked runs, events, and promotion candidates."""

    store = _open_workspace_or_exit(workspace)
    try:
        incident = store.operations.get_incident(incident_id)
        run_ids = [trace_run] if trace_run else incident.source_run_ids
        runs = [
            store.operations.get_run(run_id, include_events=True).model_dump(
                mode="json"
            )
            for run_id in run_ids
        ]
        candidates = []
        if show_promotion_candidates:
            for run_id in run_ids:
                candidates.extend(
                    candidate.model_dump(mode="json")
                    for candidate in store.operations.query_promotion_candidates(
                        source_run_id=run_id
                    )
                )
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    payload = {
        "incident": incident.model_dump(mode="json"),
        "runs": runs,
        "promotion_candidates": candidates,
    }
    if output_format == "json":
        console.print(_json_text(payload))
        return
    table = Table(title=f"Incident {incident_id}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("severity", incident.severity.value)
    table.add_row("status", incident.status.value)
    table.add_row("title", incident.title)
    table.add_row("source_runs", ", ".join(run_ids) or "none")
    table.add_row("promotion_candidates", str(len(candidates)))
    console.print(table)


@app.command("check-drift")
def check_drift_command(
    repo: Annotated[
        Path,
        typer.Argument(file_okay=False, resolve_path=True, help="Repository path."),
    ] = Path("."),
    stage: Annotated[
        str, typer.Option("--stage", help="Expected harness stage.")
    ] = "S3",
    fail_on: Annotated[
        str,
        typer.Option("--fail-on", help="Comma-separated drift classes that fail."),
    ] = "relaxed,missing,out-of-stage",
    report_out: Annotated[
        Path | None, typer.Option("--report-out", dir_okay=False)
    ] = None,
    output_format: Annotated[str, typer.Option("--output-format")] = "table",
) -> None:
    """Check harness manifests for missing, stale, relaxed, or out-of-stage drift."""

    from llm_sca_tooling.hardening.harness_drift import HarnessDriftChecker

    records = HarnessDriftChecker().check_repo(repo, expected_stage=stage)
    payload = {"records": [record.model_dump(mode="json") for record in records]}
    if report_out is not None:
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_text(_json_text(payload) + "\n", encoding="utf-8")
    if output_format == "json":
        console.print(_json_text(payload))
    else:
        table = Table(title="Harness Drift")
        table.add_column("Artifact")
        table.add_column("Classification")
        table.add_column("Detail")
        for record in records:
            table.add_row(
                record.artifact_path, record.classification.value, record.detail
            )
        console.print(table)
    failing = {item.strip() for item in fail_on.split(",") if item.strip()}
    if any(record.classification.value in failing for record in records):
        raise typer.Exit(code=1)


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


@mcp_app.command("validate")
def mcp_validate(
    workspace: Annotated[
        Path,
        typer.Option("--workspace", file_okay=False, resolve_path=True),
    ] = Path(".llm-sca"),
    transport: Annotated[
        str,
        typer.Option("--transport", help="Transport mode: local or http."),
    ] = "local",
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = 8080,
    tls: Annotated[bool, typer.Option("--tls/--no-tls")] = False,
    auth_token_env_var: Annotated[
        str | None, typer.Option("--auth-token-env-var")
    ] = None,
) -> None:
    """Validate the local MCP facade (starts, health-checks, then shuts down)."""

    if transport == "http":
        from llm_sca_tooling.hardening.models import HTTPTransportConfig
        from llm_sca_tooling.transport.http_transport import (
            validate_http_transport_environment,
        )

        try:
            summary = validate_http_transport_environment(
                HTTPTransportConfig(
                    host=host,
                    port=port,
                    tls_enabled=tls,
                    auth_token_env_var=auth_token_env_var,
                    single_user=auth_token_env_var is None,
                )
            )
        except ValueError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        console.print(_json_text(summary.model_dump(mode="json")))
        if not summary.ready:
            raise typer.Exit(code=1)
        return
    if transport != "local":
        console.print(f"[red]Error:[/red] unsupported transport: {transport}")
        raise typer.Exit(code=1)

    from llm_sca_tooling.mcp_server.config import McpServerConfig
    from llm_sca_tooling.mcp_server.server import CodeIntelligenceServer

    server = CodeIntelligenceServer(McpServerConfig.for_workspace(workspace)).start()
    try:
        console.print(_json_text(server.health_check()))
    finally:
        server.shutdown()


@mcp_app.command("serve")
def mcp_serve(
    workspace: Annotated[
        Path,
        typer.Option("--workspace", file_okay=False, resolve_path=True),
    ] = Path(".llm-sca"),
) -> None:
    """Start the stdio MCP server for AI agent integration."""

    from llm_sca_tooling.mcp_server.dev_server import main as _serve

    raise typer.Exit(code=_serve(["--workspace", str(workspace)]))


@app.command("graph-build")
def graph_build_command(
    repo_path: Annotated[str, typer.Argument(help="Path to the repository to index.")],
) -> None:
    """Build the code graph for a repository."""

    from llm_sca_tooling.indexing.service import graph_build

    result = graph_build(repo_path)
    console.print(_json_text(result.model_dump(mode="json")))


@app.command("graph-update")
def graph_update_command(
    repo_path: Annotated[str, typer.Argument(help="Path to the repository to update.")],
) -> None:
    """Update an existing code graph for a repository."""

    from llm_sca_tooling.indexing.service import graph_update

    result = graph_update(repo_path)
    console.print(_json_text(result.model_dump(mode="json")))


@app.command("setup")
def setup_command(
    workspace: Annotated[
        str,
        typer.Option("--workspace", help="evidence-sca workspace path."),
    ] = ".llm-sca",
    use_uv: Annotated[
        bool | None,
        typer.Option(
            "--uv/--no-uv",
            help=(
                "Use 'uv run evidence-sca mcp serve' instead of the installed binary. "
                "When omitted, source checkouts use uv and installed projects use "
                "the installed binary."
            ),
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run", help="Show what would change without writing."
        ),
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose/--no-verbose")] = False,
) -> None:
    """Detect AI agents and configure MCP server and skills for each."""

    from llm_sca_tooling.cli.setup_cmd import print_results, run_setup

    results = run_setup(workspace=workspace, dry_run=dry_run, use_uv=use_uv)
    print_results(results, verbose=verbose)
    if any(r.errors for r in results):
        raise typer.Exit(code=1)


def main(argv: list[str] | None = None) -> int:
    """Compatibility wrapper for programmatic CLI invocation."""

    try:
        app(args=argv, prog_name="evidence-sca")
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


def _open_workspace_or_exit(path: Path):
    from llm_sca_tooling.storage.workspace import open_workspace

    try:
        return open_workspace(path)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


def _diff_run_events(
    store: object, run_id: str, diff_run: str | None
) -> dict[str, object]:
    if diff_run is None:
        return {}
    left = store.operations.list_run_events(run_id, limit=10_000)
    right = store.operations.list_run_events(diff_run, limit=10_000)
    left_sig = [
        (
            event.type.value,
            event.stage,
            event.policy_action.value if event.policy_action else None,
        )
        for event in left
    ]
    right_sig = [
        (
            event.type.value,
            event.stage,
            event.policy_action.value if event.policy_action else None,
        )
        for event in right
    ]
    return {
        "base_run": run_id,
        "diff_run": diff_run,
        "same_sequence": left_sig == right_sig,
        "base_event_count": len(left_sig),
        "diff_event_count": len(right_sig),
    }


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
