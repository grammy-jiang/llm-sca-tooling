"""Analyser-rerun integration for sandboxed sast_repair workflows."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from llm_sca_tooling.sast_repair.models import (
    AnalyserRerunResult,
    RerunStatus,
    SandboxResult,
)

RerunCallable = Callable[[str, list[str]], Awaitable[dict[str, Any]]]


async def rerun_analyser(
    *,
    alert_id: str,
    sandbox: SandboxResult,
    analyser_id: str,
    analyser_version: str | None = None,
    changed_files: list[str] | None = None,
    runner: RerunCallable | None = None,
) -> AnalyserRerunResult:
    """Re-run the analyser on the sandbox; returns an :class:`AnalyserRerunResult`.

    ``runner`` is an injected coroutine taking ``(sandbox_path, changed_files)``
    that returns a dict with optional ``run_id`` and ``diagnostic`` keys. This
    indirection keeps the workflow analyser-agnostic and unit-testable without
    invoking real tooling (HC5).
    """
    if not sandbox.patch_applied:
        return AnalyserRerunResult(
            alert_id=alert_id,
            sandbox_snapshot_id=sandbox.sandbox_snapshot_id,
            analyser_id=analyser_id,
            analyser_version=analyser_version,
            rerun_status=RerunStatus.UNAVAILABLE,
            sarif_run_id_after=None,
            rerun_diagnostic="patch_not_applied",
            wall_ms=0,
        )

    if runner is None:
        return AnalyserRerunResult(
            alert_id=alert_id,
            sandbox_snapshot_id=sandbox.sandbox_snapshot_id,
            analyser_id=analyser_id,
            analyser_version=analyser_version,
            rerun_status=RerunStatus.UNAVAILABLE,
            sarif_run_id_after=None,
            rerun_diagnostic="no_runner_injected",
            wall_ms=0,
        )

    started = time.monotonic()
    try:
        payload = await runner(sandbox.sandbox_path, list(changed_files or []))
    except (TimeoutError, OSError, RuntimeError) as exc:
        return AnalyserRerunResult(
            alert_id=alert_id,
            sandbox_snapshot_id=sandbox.sandbox_snapshot_id,
            analyser_id=analyser_id,
            analyser_version=analyser_version,
            rerun_status=RerunStatus.FAILED,
            rerun_diagnostic=f"runner_error:{exc}",
            wall_ms=int((time.monotonic() - started) * 1000),
        )
    wall_ms = int((time.monotonic() - started) * 1000)
    diagnostic = str(payload.get("diagnostic")) if payload.get("diagnostic") else None
    if changed_files is None:
        diagnostic = diagnostic or "rerun_full_repo"
    return AnalyserRerunResult(
        alert_id=alert_id,
        sandbox_snapshot_id=sandbox.sandbox_snapshot_id,
        analyser_id=analyser_id,
        analyser_version=analyser_version or str(payload.get("version") or ""),
        rerun_status=RerunStatus.OK,
        sarif_run_id_after=(
            str(payload.get("run_id")) if payload.get("run_id") else None
        ),
        rerun_diagnostic=diagnostic,
        wall_ms=wall_ms,
    )


__all__ = ["rerun_analyser", "RerunCallable"]
