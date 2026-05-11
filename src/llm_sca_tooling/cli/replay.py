"""Session replay CLI command.

Reconstructs and displays a run record's event sequence from the
operational store.  Output is idempotent for the same run record.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

__all__ = ["replay_app"]

replay_app = typer.Typer(help="Replay session run records.")
_console = Console()
_err = Console(stderr=True)


def _load_run(run_id: str, runs_dir: Path) -> dict[str, Any] | None:
    """Load a run record from ``.agent/runs/<run_id>/record.json``."""
    record_path = runs_dir / run_id / "record.json"
    if not record_path.exists():
        return None
    try:
        data: Any = json.loads(record_path.read_text(encoding="utf-8"))
        return dict(data) if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _load_events(run_id: str, runs_dir: Path) -> list[dict[str, Any]]:
    """Load run events from ``.agent/runs/<run_id>/events.jsonl``."""
    events_path = runs_dir / run_id / "events.jsonl"
    if not events_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj: Any = json.loads(line)
            if isinstance(obj, dict):
                events.append(obj)
        except json.JSONDecodeError:
            pass
    return events


@replay_app.command("run")
def replay_run(
    run_id: str = typer.Argument(..., help="Run ID to replay."),
    show_events: bool = typer.Option(False, "--show-events", help="Show all events."),
    filter_stage: str | None = typer.Option(None, "--filter-stage"),
    filter_type: str | None = typer.Option(None, "--filter-type"),
    diff_run: str | None = typer.Option(None, "--diff-run"),
    output_format: str = typer.Option("rich", "--output-format"),
    runs_dir: Path = typer.Option(Path(".agent/runs"), "--runs-dir"),  # noqa: B008
) -> None:
    """Replay the event sequence for RUN_ID."""
    record = _load_run(run_id, runs_dir)
    if record is None:
        _err.print(f"[red]Run record not found:[/red] {run_id}")
        raise typer.Exit(code=1)

    events = _load_events(run_id, runs_dir)

    # Apply filters
    if filter_stage:
        events = [e for e in events if e.get("stage") == filter_stage]
    if filter_type:
        events = [e for e in events if e.get("type") == filter_type]

    # Sort chronologically
    events.sort(key=lambda e: e.get("ts", ""))

    if output_format == "json":
        import orjson  # noqa: PLC0415

        payload: dict[str, Any] = {"run_id": run_id, "record": record, "events": events}
        _console.print(orjson.dumps(payload).decode())
        return

    # Rich output
    table = Table(title=f"Run: {run_id}", show_header=True)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    for k, v in record.items():
        table.add_row(str(k), str(v))
    _console.print(table)

    if show_events or events:
        ev_table = Table(title="Events", show_header=True)
        ev_table.add_column("#")
        ev_table.add_column("ts")
        ev_table.add_column("type")
        ev_table.add_column("detail")
        for i, ev in enumerate(events):
            ev_table.add_row(
                str(i),
                str(ev.get("ts", "")),
                str(ev.get("type", "")),
                str(ev.get("detail", ev.get("message", ""))),
            )
        _console.print(ev_table)

    if diff_run:
        other_events = _load_events(diff_run, runs_dir)
        other_events.sort(key=lambda e: e.get("ts", ""))
        _console.print(
            f"\n[yellow]Diff vs {diff_run}:[/yellow] "
            f"{len(events)} events vs {len(other_events)} events"
        )
