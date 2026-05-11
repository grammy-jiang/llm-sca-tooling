"""Benchmark release report templates and mandatory reporting checks."""

from __future__ import annotations

from llm_sca_tooling.release.models import (
    CalibrationReport,
    OperationalHarnessGateResult,
    ReleaseGateResult,
)

__all__ = [
    "MANDATORY_REPORTING_RULES",
    "missing_mandatory_sections",
    "render_release_report",
]

MANDATORY_REPORTING_RULES = [
    "swe-bench-live headline suite",
    "suite median age",
    "poc-plus pass-rate",
    "swd-bench file-location acceptance",
    "no llm-as-judge substitute",
    "fl-conditioned repair rate",
    "rds v0.2 six-axis vector",
    "operational metrics beside task metrics",
]


def render_release_report(
    *,
    result: ReleaseGateResult,
    calibration: CalibrationReport | None,
    operational: OperationalHarnessGateResult | None,
) -> str:
    benchmark_lines = [
        f"| {item.suite_id} | {item.status} | {item.passed} |"
        for item in result.benchmark_results
    ]
    calibration_line = (
        "Calibration unavailable"
        if calibration is None
        else (
            f"patch-risk ECE={calibration.patch_risk_ece:.3f}; "
            f"impl-check families={len(calibration.impl_check_ece_per_clause_family)}; "
            f"repo-QA file-loc={calibration.repo_qa_file_loc_accuracy:.3f}; "
            f"memory delta pp={calibration.memory_her_eviction_delta_pp:.1f}"
        )
    )
    operational_line = (
        "Operational metrics unavailable"
        if operational is None
        else (
            f"process-compliance={operational.policy_compliance_rate:.3f}; "
            f"trace-replay={operational.trace_replay_success_rate:.3f}; "
            f"policy violations={operational.policy_violation_count}; "
            f"budget hard-stops={operational.budget_hard_stop_count}; "
            f"incident recidivism={operational.incident_recidivism_rate:.3f}; "
            f"cost per accepted verdict={operational.cost_per_accepted_verdict:.1f}"
        )
    )
    rules = "\n".join(f"- {rule}" for rule in MANDATORY_REPORTING_RULES)
    return "\n".join(
        [
            "# Release Gate Report",
            "",
            "## Harness Condition Sheet",
            f"- harness_condition_id: {result.harness_condition_id}",
            f"- ai_readiness_report_ref: {result.ai_readiness_report_ref}",
            "",
            "## Benchmark Results",
            "| suite | status | passed |",
            "|---|---|---|",
            *benchmark_lines,
            "",
            "## Calibration",
            calibration_line,
            "",
            "## Operational Metrics",
            operational_line,
            "",
            "## AI-Readiness",
            str(result.ai_readiness_report_ref or "missing"),
            "",
            "## Adversarial Checks",
            f"passed={all(item.passed for item in result.adversarial_check_results)}",
            "",
            "## Mandatory Reporting Rules",
            rules,
            "",
            "## Known Limitations",
            "- Fixture/null-mode reports are not external-quality benchmark claims.",
        ]
    )


def missing_mandatory_sections(report_text: str) -> list[str]:
    required = [
        "Harness Condition Sheet",
        "Benchmark Results",
        "Calibration",
        "Operational Metrics",
        "AI-Readiness",
        "Adversarial Checks",
        "Mandatory Reporting Rules",
        "Known Limitations",
    ]
    missing = [section for section in required if section not in report_text]
    missing.extend(
        rule for rule in MANDATORY_REPORTING_RULES if rule not in report_text
    )
    return missing
