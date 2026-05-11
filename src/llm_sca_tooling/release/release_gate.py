"""Release gate aggregation and JSON report writing."""

from __future__ import annotations

from pathlib import Path

import orjson

from llm_sca_tooling.release.adversarial import run_adversarial_suite
from llm_sca_tooling.release.calibration import build_calibration_report
from llm_sca_tooling.release.models import (
    AblationReport,
    AdversarialCheckResult,
    BenchmarkSuiteResult,
    CalibrationReport,
    CalibrationSample,
    OperationalHarnessGateResult,
    ReleaseGateResult,
    ReleaseImpact,
)

__all__ = [
    "ReleaseGateEvaluator",
    "build_passing_fixture_release_gate",
    "write_release_gate_report",
]


class ReleaseGateEvaluator:
    """Aggregate Phase 18 benchmark, calibration, and operational gates."""

    def evaluate(
        self,
        *,
        harness_condition_id: str,
        benchmark_results: list[BenchmarkSuiteResult],
        calibration_report: CalibrationReport | None = None,
        ablation_report: AblationReport | None = None,
        operational_gate_result: OperationalHarnessGateResult | None = None,
        adversarial_check_results: list[AdversarialCheckResult] | None = None,
        memory_ship_gate_result_ref: str | None = None,
        ai_readiness_report_ref: str | None = None,
        calibration_required: bool = True,
        adversarial_required: bool = True,
        memory_gate_required: bool = True,
        operational_gate_required: bool = True,
        fail_on_any: bool = True,
    ) -> ReleaseGateResult:
        failing: list[str] = []
        disabled: list[str] = []
        recommendations: list[str] = []
        adversarial_results = adversarial_check_results or []
        if any(not result.passed for result in benchmark_results):
            failing.append("benchmarks")
        if calibration_required:
            if calibration_report is None:
                failing.append("calibration")
                recommendations.append("Attach a CalibrationReport.")
            elif not _calibration_passed(calibration_report):
                failing.append("calibration")
                recommendations.append("Recalibrate failing model or workflow family.")
        else:
            disabled.append("calibration")
        if adversarial_required:
            if not adversarial_results or any(
                not result.passed for result in adversarial_results
            ):
                failing.append("adversarial")
                recommendations.append("Fix failing adversarial checks.")
        else:
            disabled.append("adversarial")
        if operational_gate_required:
            if (
                operational_gate_result is None
                or not operational_gate_result.gate_passed
            ):
                failing.append("operational")
                recommendations.append("Resolve operational harness gate failures.")
        else:
            disabled.append("operational")
        if memory_gate_required:
            if (
                calibration_report is None
                or not calibration_report.memory_ship_gate_passed
            ):
                failing.append("memory")
                recommendations.append(
                    "Keep memory disabled until the ship gate passes."
                )
        else:
            disabled.append("memory")
        if ablation_report is not None and ablation_report.release_impact in {
            ReleaseImpact.unexpected_improvement,
            ReleaseImpact.unexpected_degradation,
        }:
            failing.append("ablation")
            recommendations.append("Investigate ablation anomalies before release.")
        if ai_readiness_report_ref is None:
            failing.append("ai_readiness")
            recommendations.append("Attach an AI-readiness report.")
        overall_pass = not failing if fail_on_any else not set(failing) - {"benchmarks"}
        return ReleaseGateResult(
            harness_condition_id=harness_condition_id,
            benchmark_results=benchmark_results,
            calibration_report_ref=(
                calibration_report.report_id if calibration_report is not None else None
            ),
            ablation_report_ref=(
                ablation_report.report_id if ablation_report is not None else None
            ),
            operational_gate_result_ref=(
                operational_gate_result.gate_id
                if operational_gate_result is not None
                else None
            ),
            adversarial_check_results=adversarial_results,
            memory_ship_gate_result_ref=memory_ship_gate_result_ref,
            ai_readiness_report_ref=ai_readiness_report_ref,
            disabled_gates=disabled,
            overall_pass=overall_pass,
            failing_gates=failing,
            recommendations=recommendations,
        )


def build_passing_fixture_release_gate(
    *,
    suite: str = "all",
    calibration_required: bool = True,
    adversarial_required: bool = True,
    memory_gate_required: bool = True,
    operational_gate_required: bool = True,
    fail_on_any: bool = True,
) -> ReleaseGateResult:
    benchmark_results = [
        BenchmarkSuiteResult(
            suite_id=item,
            eval_run_id=f"eval:{item}:fixture",
            status="completed",
            passed=True,
            metrics={"resolve_rate": 1.0, "fl_conditioned_repair_rate": 1.0},
            freshness_days=10.0,
        )
        for item in _suite_ids(suite)
    ]
    calibration = build_calibration_report(
        eval_run_id="eval:phase18:fixture",
        model_backend="null",
        harness_condition_id="hcs:phase18:fixture",
        patch_risk_samples=[
            _sample("patch:1", 0.95, "safe", "safe"),
            _sample("patch:2", 0.95, "vulnerable", "vulnerable"),
            _sample("patch:3", 0.95, "correct-but-overfit", "correct-but-overfit"),
        ],
        impl_check_samples=[
            _sample("clause:1", 0.95, "satisfied", "satisfied"),
            _sample("clause:2", 0.95, "violated", "violated"),
            _sample("clause:3", 0.95, "unknown", "unknown"),
        ],
        repo_qa_file_loc_accuracy=0.95,
        repo_qa_behaviour_tracing_accuracy=0.75,
        memory_her_eviction_delta_pp=3.5,
        rds_v2_summary={"suite": "fixture"},
    )
    from llm_sca_tooling.release.operational_gates import (
        compute_operational_harness_gate,
    )

    operational = compute_operational_harness_gate(
        eval_run_id="eval:phase18:fixture",
        run_records=[
            {
                "trace_complete": True,
                "policy_compliant": True,
                "budget_reliable": True,
                "maintainability_oracle_passed": True,
                "manifest_regression_passed": True,
                "trace_replay_success": True,
                "accepted_verdict": True,
            }
            for _ in range(10)
        ],
        readiness_threshold_met=True,
    )
    adversarial = run_adversarial_suite()
    return ReleaseGateEvaluator().evaluate(
        harness_condition_id="hcs:phase18:fixture",
        benchmark_results=benchmark_results,
        calibration_report=calibration,
        operational_gate_result=operational,
        adversarial_check_results=adversarial,
        memory_ship_gate_result_ref="memory-ship-gate:phase18:fixture",
        ai_readiness_report_ref="readiness:phase18:fixture",
        calibration_required=calibration_required,
        adversarial_required=adversarial_required,
        memory_gate_required=memory_gate_required,
        operational_gate_required=operational_gate_required,
        fail_on_any=fail_on_any,
    )


def write_release_gate_report(result: ReleaseGateResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        orjson.dumps(result.model_dump(mode="json"), option=orjson.OPT_INDENT_2)
    )


def _calibration_passed(report: CalibrationReport) -> bool:
    return (
        report.patch_risk_gate_passed
        and report.impl_check_gate_passed
        and report.repo_qa_behaviour_gate_passed
    )


def _suite_ids(suite: str) -> list[str]:
    suite = suite.lower()
    if suite == "all":
        return ["t1", "t2", "t3", "t4"]
    if suite not in {"t1", "t2", "t3", "t4"}:
        raise ValueError("suite must be one of: t1, t2, t3, t4, all")
    return [suite]


def _sample(
    sample_id: str,
    probability: float,
    predicted: str,
    gold: str,
) -> CalibrationSample:
    return CalibrationSample(
        sample_id=sample_id,
        family="fixture",
        predicted_probability=probability,
        predicted_label=predicted,
        gold_label=gold,
    )
