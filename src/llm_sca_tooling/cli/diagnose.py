"""Incident diagnosis CLI command.

Reads an incident record and displays its full timeline, root cause,
containment, remediation, and linked run events.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

__all__ = ["diagnose_app"]

diagnose_app = typer.Typer(help="Diagnose incidents and run records.")
_console = Console()
_err = Console(stderr=True)

_INCIDENTS_DIR = Path(".agent/incidents")


def _load_incident(incident_id: str, incidents_dir: Path) -> dict[str, Any] | None:
    incident_path = incidents_dir / f"{incident_id}.json"
    if not incident_path.exists():
        return None
    try:
        data: Any = json.loads(incident_path.read_text(encoding="utf-8"))
        return dict(data) if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


@diagnose_app.command("incident")
def diagnose_incident(
    incident_id: str = typer.Argument(..., help="Incident ID to diagnose."),
    trace_run: bool = typer.Option(False, "--trace-run", help="Replay the linked run."),
    show_promotion_candidates: bool = typer.Option(
        False, "--show-promotion-candidates"
    ),
    output_format: str = typer.Option("rich", "--output-format"),
    incidents_dir: Path = typer.Option(_INCIDENTS_DIR, "--incidents-dir"),  # noqa: B008
    runs_dir: Path = typer.Option(Path(".agent/runs"), "--runs-dir"),  # noqa: B008
) -> None:
    """Diagnose INCIDENT_ID — display timeline, root cause, and linked events."""
    incident = _load_incident(incident_id, incidents_dir)
    if incident is None:
        _err.print(f"[red]Incident not found:[/red] {incident_id}")
        raise typer.Exit(code=1)

    if output_format == "json":
        import orjson  # noqa: PLC0415

        _console.print(orjson.dumps(incident).decode())
        return

    # Summary table
    table = Table(title=f"Incident: {incident_id}", show_header=True)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    for field_name in (
        "severity",
        "status",
        "impact",
        "root_cause",
        "containment",
        "remediation",
        "opened_at",
        "closed_at",
        "reviewer",
    ):
        table.add_row(field_name, str(incident.get(field_name, "")))
    _console.print(table)

    # Timeline
    timeline = incident.get("timeline", [])
    if timeline:
        tl_table = Table(title="Timeline", show_header=True)
        tl_table.add_column("ts")
        tl_table.add_column("event")
        for entry in timeline:
            tl_table.add_row(str(entry.get("ts", "")), str(entry.get("event", "")))
        _console.print(tl_table)

    # Linked runs
    linked_run = incident.get("run_id")
    if linked_run and trace_run:
        from llm_sca_tooling.cli.replay import _load_events  # noqa: PLC0415

        events = _load_events(linked_run, runs_dir)
        ev_table = Table(title=f"Linked run events: {linked_run}", show_header=True)
        ev_table.add_column("#")
        ev_table.add_column("ts")
        ev_table.add_column("type")
        ev_table.add_column("detail")
        for i, ev in enumerate(events):
            ev_table.add_row(
                str(i),
                str(ev.get("ts", "")),
                str(ev.get("type", "")),
                str(ev.get("detail", "")),
            )
        _console.print(ev_table)

    # Promotion candidates
    if show_promotion_candidates:
        candidates = incident.get("promotion_candidates", [])
        if candidates:
            pc_table = Table(title="Promotion Candidates", show_header=True)
            pc_table.add_column("lesson")
            pc_table.add_column("status")
            for c in candidates:
                pc_table.add_row(str(c.get("lesson", "")), str(c.get("status", "")))
            _console.print(pc_table)
        else:
            _console.print("[dim]No promotion candidates found.[/dim]")
