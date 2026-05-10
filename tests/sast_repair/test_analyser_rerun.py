"""Tests for analyser-rerun integration."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.sast_repair.analyser_rerun import rerun_analyser
from llm_sca_tooling.sast_repair.models import RerunStatus, SandboxResult


def _sandbox(applied: bool = True) -> SandboxResult:
    return SandboxResult(
        alert_id="a1",
        sandbox_path="/tmp/sb-test",  # noqa: S108 - test fixture only
        patch_applied=applied,
        sandbox_snapshot_id="sb:1" if applied else None,
    )


async def test_rerun_unavailable_when_patch_not_applied() -> None:
    result = await rerun_analyser(
        alert_id="a1", sandbox=_sandbox(False), analyser_id="semgrep"
    )
    assert result.rerun_status is RerunStatus.UNAVAILABLE
    assert result.rerun_diagnostic == "patch_not_applied"


async def test_rerun_unavailable_when_no_runner() -> None:
    result = await rerun_analyser(
        alert_id="a1", sandbox=_sandbox(True), analyser_id="semgrep"
    )
    assert result.rerun_status is RerunStatus.UNAVAILABLE
    assert result.rerun_diagnostic == "no_runner_injected"


async def test_rerun_ok_with_runner() -> None:
    async def runner(path: str, files: list[str]) -> dict[str, Any]:
        return {"run_id": "rerun:1", "version": "1.2.3"}

    result = await rerun_analyser(
        alert_id="a1",
        sandbox=_sandbox(True),
        analyser_id="semgrep",
        runner=runner,
    )
    assert result.rerun_status is RerunStatus.OK
    assert result.sarif_run_id_after == "rerun:1"
    assert result.analyser_version == "1.2.3"


async def test_rerun_failed_when_runner_raises() -> None:
    async def runner(path: str, files: list[str]) -> dict[str, Any]:
        raise RuntimeError("boom")

    result = await rerun_analyser(
        alert_id="a1",
        sandbox=_sandbox(True),
        analyser_id="semgrep",
        runner=runner,
    )
    assert result.rerun_status is RerunStatus.FAILED
    assert result.rerun_diagnostic and "boom" in result.rerun_diagnostic


async def test_rerun_full_repo_diagnostic_when_no_changed_files() -> None:
    async def runner(path: str, files: list[str]) -> dict[str, Any]:
        return {"run_id": "r"}

    result = await rerun_analyser(
        alert_id="a1",
        sandbox=_sandbox(True),
        analyser_id="semgrep",
        runner=runner,
        changed_files=None,
    )
    assert result.rerun_diagnostic == "rerun_full_repo"
