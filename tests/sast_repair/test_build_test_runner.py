"""Tests for build/test rerun integration."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.sast_repair.build_test_runner import run_build_and_tests


async def test_build_test_no_runner() -> None:
    result = await run_build_and_tests(
        alert_id="a1", sandbox_path="/sb", changed_files=["src/x.py"]
    )
    assert result.build_status == "unavailable"
    codes = {d["code"] for d in result.diagnostics}
    assert "no_runner_injected" in codes


async def test_build_test_coverage_absent() -> None:
    async def runner(path: str, scope: list[str]) -> dict[str, Any]:
        return {"build_status": "ok", "test_run_status": "passed"}

    result = await run_build_and_tests(
        alert_id="a1",
        sandbox_path="/sb",
        changed_files=["src/x.py"],
        coverage_map={"other.py": ["t1"]},
        runner=runner,
    )
    codes = {d["code"] for d in result.diagnostics}
    assert "test_coverage_absent" in codes
    assert result.build_status == "ok"


async def test_build_test_coverage_data_unavailable() -> None:
    async def runner(path: str, scope: list[str]) -> dict[str, Any]:
        return {"build_status": "ok", "test_run_status": "passed"}

    result = await run_build_and_tests(
        alert_id="a1",
        sandbox_path="/sb",
        changed_files=["src/x.py"],
        runner=runner,
    )
    codes = {d["code"] for d in result.diagnostics}
    assert "coverage_data_unavailable" in codes


async def test_build_test_runner_error() -> None:
    async def runner(path: str, scope: list[str]) -> dict[str, Any]:
        raise OSError("io")

    result = await run_build_and_tests(alert_id="a1", sandbox_path="/sb", runner=runner)
    assert result.build_status == "failed"
    assert any(d["code"] == "runner_error" for d in result.diagnostics)


async def test_build_test_reproduction_executed() -> None:
    async def runner(path: str, scope: list[str]) -> dict[str, Any]:
        return {
            "build_status": "ok",
            "test_run_status": "passed",
            "reproduction": True,
            "reproduction_test_result": "passed",
            "newly_passing_tests": ["t1"],
            "flaky_tests_detected": ["t2"],
        }

    result = await run_build_and_tests(
        alert_id="a1",
        sandbox_path="/sb",
        runner=runner,
        reproduction_test="t_repro",
    )
    assert result.reproduction_test_executed is True
    assert result.reproduction_test_result == "passed"
    assert result.newly_passing_tests == ["t1"]
    assert "t2" in result.flaky_tests_detected
