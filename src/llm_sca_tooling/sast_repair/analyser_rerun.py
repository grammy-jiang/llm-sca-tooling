"""Analyser rerun stub."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.models import AnalyserRerunResult, SandboxResult


def rerun_analyser(
    *, alert_id: str, sandbox: SandboxResult, analyser_id: str = "null-analyser"
) -> AnalyserRerunResult:
    return AnalyserRerunResult(
        alert_id=alert_id,
        sandbox_snapshot_id=sandbox.sandbox_snapshot_id,
        analyser_id=analyser_id,
        analyser_version="phase12-null",
        rerun_status="completed",
        sarif_run_id_after=f"sarif-after:{alert_id}",
        rerun_diagnostic="null-mode rerun",
    )
