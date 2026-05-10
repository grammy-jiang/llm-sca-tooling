"""Release gate aggregation."""

from __future__ import annotations

import uuid

from llm_sca_tooling.release.models import (
    AdversarialCheckResult,
    CalibrationReport,
    OperationalHarnessGateResult,
    ReleaseGateResult,
)
from llm_sca_tooling.schemas.base import JsonObject


def run_release_gate(
    *,
    harness_condition_id: str,
    benchmark_results: dict[str, JsonObject],
    calibration_report: CalibrationReport | None = None,
    operational_gate: OperationalHarnessGateResult | None = None,
    adversarial_results: list[AdversarialCheckResult] | None = None,
    calibration_required: bool = True,
    operational_required: bool = True,
    adversarial_required: bool = True,
    memory_gate_required: bool = True,
    ai_readiness_report_ref: str | None = None,
) -> ReleaseGateResult:
    failing: list[str] = []
    if calibration_required:
        if calibration_report is None:
            failing.append("calibration_missing")
        else:
            if not calibration_report.patch_risk_gate_passed:
                failing.append("patch_risk_calibration")
            if not calibration_report.impl_check_gate_passed:
                failing.append("impl_check_calibration")
            if memory_gate_required and not calibration_report.memory_ship_gate_passed:
                failing.append("memory_ship_gate")
    if operational_required and (
        operational_gate is None or not operational_gate.gate_passed
    ):
        failing.append("operational_gate")
    if adversarial_required and (
        not adversarial_results
        or any(not result.passed for result in adversarial_results)
    ):
        failing.append("adversarial_checks")
    for suite, result in benchmark_results.items():
        if not bool(result.get("passed", False)):
            failing.append(f"benchmark:{suite}")
    return ReleaseGateResult(
        gate_run_id=f"release-gate:{uuid.uuid4().hex}",
        harness_condition_id=harness_condition_id,
        benchmark_results=benchmark_results,
        calibration_report_ref=(
            calibration_report.report_id if calibration_report else None
        ),
        operational_gate_result_ref=(
            operational_gate.gate_id if operational_gate else None
        ),
        adversarial_check_results=adversarial_results or [],
        memory_ship_gate_result_ref=(
            calibration_report.report_id
            if calibration_report and calibration_report.memory_ship_gate_passed
            else None
        ),
        ai_readiness_report_ref=ai_readiness_report_ref,
        overall_pass=not failing,
        failing_gates=failing,
        recommendations=[f"fix {gate}" for gate in failing],
    )
