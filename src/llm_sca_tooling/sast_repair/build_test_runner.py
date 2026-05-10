"""Build/test rerun integration."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from llm_sca_tooling.sast_repair.models import BuildTestResult

BuildTestRunner = Callable[[str, list[str]], Awaitable[dict[str, Any]]]


async def run_build_and_tests(
    *,
    alert_id: str,
    sandbox_path: str,
    sandbox_snapshot_id: str | None = None,
    changed_files: list[str] | None = None,
    coverage_map: dict[str, list[str]] | None = None,
    runner: BuildTestRunner | None = None,
    flaky_tests: list[str] | None = None,
    reproduction_test: str | None = None,
) -> BuildTestResult:
    """Drive a build/test rerun against a sandbox and emit a typed result.

    ``coverage_map`` maps changed files to test IDs that exercise them.
    When ``coverage_map`` is empty for the changed files, a diagnostic is
    emitted and the runner is invoked without a scope.
    """
    diagnostics: list[dict[str, Any]] = []
    scope: list[str] = []
    if changed_files and coverage_map:
        for file_path in changed_files:
            scope.extend(coverage_map.get(file_path, []))
        if not scope:
            diagnostics.append({"code": "test_coverage_absent"})
    elif coverage_map is None:
        diagnostics.append({"code": "coverage_data_unavailable"})
    if runner is None:
        return BuildTestResult(
            alert_id=alert_id,
            sandbox_snapshot_id=sandbox_snapshot_id,
            build_status="unavailable",
            test_run_status="unavailable",
            newly_failing_tests=[],
            newly_passing_tests=[],
            flaky_tests_detected=list(flaky_tests or []),
            reproduction_test_executed=False,
            reproduction_test_result=None,
            wall_ms=0,
            diagnostics=diagnostics + [{"code": "no_runner_injected"}],
        )

    started = time.monotonic()
    try:
        payload = await runner(sandbox_path, scope)
    except (TimeoutError, OSError, RuntimeError) as exc:
        return BuildTestResult(
            alert_id=alert_id,
            sandbox_snapshot_id=sandbox_snapshot_id,
            build_status="failed",
            test_run_status="failed",
            newly_failing_tests=[],
            newly_passing_tests=[],
            flaky_tests_detected=list(flaky_tests or []),
            reproduction_test_executed=False,
            reproduction_test_result=None,
            wall_ms=int((time.monotonic() - started) * 1000),
            diagnostics=diagnostics + [{"code": "runner_error", "message": str(exc)}],
        )
    wall_ms = int((time.monotonic() - started) * 1000)
    repro_executed = bool(reproduction_test) and bool(payload.get("reproduction"))
    return BuildTestResult(
        alert_id=alert_id,
        sandbox_snapshot_id=sandbox_snapshot_id,
        build_status=str(payload.get("build_status", "unknown")),
        test_run_status=str(payload.get("test_run_status", "unknown")),
        newly_failing_tests=list(payload.get("newly_failing_tests") or []),
        newly_passing_tests=list(payload.get("newly_passing_tests") or []),
        flaky_tests_detected=list(
            payload.get("flaky_tests_detected") or flaky_tests or []
        ),
        reproduction_test_executed=repro_executed,
        reproduction_test_result=payload.get("reproduction_test_result"),
        wall_ms=wall_ms,
        diagnostics=diagnostics,
    )


__all__ = ["run_build_and_tests", "BuildTestRunner"]
