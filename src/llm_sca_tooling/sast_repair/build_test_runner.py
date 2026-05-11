"""Build/test rerun integration stub."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.models import BuildTestResult, SandboxResult


def run_build_and_tests(
    *,
    alert_id: str,
    sandbox: SandboxResult,
    newly_failing_tests: list[str] | None = None,
) -> BuildTestResult:
    failures = newly_failing_tests or []
    return BuildTestResult(
        alert_id=alert_id,
        sandbox_snapshot_id=sandbox.sandbox_snapshot_id,
        build_status="passed",
        test_run_status="failed" if failures else "passed",
        newly_failing_tests=failures,
        diagnostics=[] if failures else ["coverage unavailable; null-mode pass"],
    )
