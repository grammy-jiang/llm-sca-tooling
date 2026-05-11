"""Release automation CLI commands (Phase 19).

Wraps the Phase 18 release gate with harness drift check and manifest
regression runner integration.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

__all__ = ["release_app"]

release_app = typer.Typer(help="Release automation commands.")
_console = Console()
_err = Console(stderr=True)


@release_app.command("gate")
def release_gate_p19(
    suite: str = typer.Option("all", "--suite"),
    fail_on_any: bool = typer.Option(False, "--fail-on-any"),
    check_drift: bool = typer.Option(True, "--check-drift/--no-check-drift"),
    check_manifest_regression: bool = typer.Option(
        True, "--check-manifest/--no-check-manifest"
    ),
    report_out: Path | None = typer.Option(None, "--report-out"),
    stage: str = typer.Option("S0", "--stage", help="Harness stage for drift check."),
) -> None:
    """Run the full Phase 19 release gate.

    Includes Phase 18 release gate, harness drift check, and manifest
    regression check.
    """
    from llm_sca_tooling.hardening.harness_drift import (  # noqa: PLC0415
        HarnessDriftChecker,
    )
    from llm_sca_tooling.release.release_gate import (  # noqa: PLC0415
        build_passing_fixture_release_gate,
        write_release_gate_report,
    )

    any_failure = False

    # --- Phase 18 release gate ---
    try:
        result = build_passing_fixture_release_gate(
            suite=suite,
            fail_on_any=fail_on_any,
        )
    except ValueError as exc:
        _err.print(f"[red]Release gate error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if report_out is not None:
        write_release_gate_report(result, report_out)

    if not result.overall_pass:
        _err.print("[red]Phase 18 release gate FAILED[/red]")
        any_failure = True

    # --- Harness drift check ---
    if check_drift:

        valid_stages = ("S0", "S1", "S2", "S3")
        if stage not in valid_stages:
            _err.print(
                f"[red]Invalid stage {stage!r}; must be one of {valid_stages}[/red]"
            )
            raise typer.Exit(code=2)

        checker = HarnessDriftChecker()
        drift_report = checker.check(stage=stage)  # type: ignore[arg-type]
        drift_table = Table(title="Harness Drift", show_header=True)
        drift_table.add_column("Artefact", style="cyan")
        drift_table.add_column("Status")
        drift_table.add_column("Detail")
        for rec in drift_report.records:
            colour = "green" if rec.drift_class == "clean" else "red"
            drift_table.add_row(
                rec.artefact,
                f"[{colour}]{rec.drift_class}[/{colour}]",
                rec.detail,
            )
        _console.print(drift_table)
        if drift_report.has_relaxed:
            _err.print("[red]Drift check: RELAXED constraints detected — BLOCKED[/red]")
            any_failure = True

    # --- Manifest regression ---
    if check_manifest_regression:
        from llm_sca_tooling.hardening.manifest_regression_runner import (  # noqa: PLC0415
            ManifestRegressionRunner,
        )

        runner = ManifestRegressionRunner()
        # Collect AGENTS.md as a key artefact to check
        artefacts: dict[str, str] = {}
        for fname in ("AGENTS.md", "CLAUDE.md"):
            p = Path(fname)
            if p.exists():
                artefacts[fname] = p.read_text(encoding="utf-8")

        reg_report = runner.run(artefacts)
        if reg_report.blocks_release:
            _err.print("[red]Manifest regression: BLOCKING findings detected[/red]")
            any_failure = True

    # --- Summary ---
    table = Table(title="Release Gate Summary", show_header=True)
    table.add_column("Gate", style="cyan")
    table.add_column("Result")
    table.add_row(
        "Phase 18 gate",
        "[green]PASS[/green]" if result.overall_pass else "[red]FAIL[/red]",
    )
    if check_drift:
        d_ok = not drift_report.has_relaxed
        table.add_row(
            "Harness drift",
            "[green]PASS[/green]" if d_ok else "[red]FAIL[/red]",
        )
    if check_manifest_regression:
        m_ok = not reg_report.blocks_release
        table.add_row(
            "Manifest regression",
            "[green]PASS[/green]" if m_ok else "[red]FAIL[/red]",
        )
    _console.print(table)

    if any_failure:
        raise typer.Exit(code=1)


@release_app.command("check-drift")
def check_drift(
    repo: str = typer.Argument(".", help="Repo path to check."),
    stage: str = typer.Option("S0", "--stage"),
    fail_on: str = typer.Option(
        "relaxed", "--fail-on", help="Fail on: missing|stale|relaxed|any"
    ),
    report_out: Path | None = typer.Option(None, "--report-out"),
) -> None:
    """Check harness drift for REPO."""
    from llm_sca_tooling.hardening.harness_drift import (  # noqa: PLC0415
        HarnessDriftChecker,
    )

    valid_stages = ("S0", "S1", "S2", "S3")
    if stage not in valid_stages:
        _err.print(f"[red]Invalid stage {stage!r}[/red]")
        raise typer.Exit(code=2)

    checker = HarnessDriftChecker(repo_root=repo)
    report = checker.check(stage=stage)  # type: ignore[arg-type]

    if report_out is not None:
        import json  # noqa: PLC0415

        report_out.write_text(
            json.dumps(
                [
                    {
                        "artefact": r.artefact,
                        "drift_class": r.drift_class,
                        "detail": r.detail,
                    }
                    for r in report.records
                ],
                indent=2,
            ),
            encoding="utf-8",
        )

    table = Table(title=f"Drift Report: {repo} (stage={stage})", show_header=True)
    table.add_column("Artefact", style="cyan")
    table.add_column("Class")
    table.add_column("Detail")
    for rec in report.records:
        colour = "green" if rec.drift_class == "clean" else "red"
        table.add_row(
            rec.artefact,
            f"[{colour}]{rec.drift_class}[/{colour}]",
            rec.detail,
        )
    _console.print(table)

    should_fail = False
    if fail_on == "any":
        should_fail = not report.is_clean
    elif fail_on == "relaxed":
        should_fail = report.has_relaxed
    elif fail_on == "missing":
        should_fail = report.has_missing
    elif fail_on == "stale":
        should_fail = any(r.drift_class == "stale" for r in report.records)

    if should_fail:
        _err.print(f"[red]Drift check failed (fail-on={fail_on!r})[/red]")
        raise typer.Exit(code=1)
