"""Release report template rendering and checks."""

from __future__ import annotations

from llm_sca_tooling.release.models import ReleaseGateResult

MANDATORY_SECTIONS = [
    "Harness Condition Sheet",
    "Benchmark results",
    "Calibration",
    "Operational metrics",
    "AI-readiness",
    "Adversarial checks",
    "Known limitations",
]


def render_release_report(result: ReleaseGateResult) -> str:
    return "\n".join(
        [
            "# Release Report",
            "## Harness Condition Sheet",
            result.harness_condition_id,
            "## Benchmark results",
            str(sorted(result.benchmark_results)),
            "## Calibration",
            str(result.calibration_report_ref),
            "## Operational metrics",
            str(result.operational_gate_result_ref),
            "## AI-readiness",
            str(result.ai_readiness_report_ref),
            "## Adversarial checks",
            str(len(result.adversarial_check_results)),
            "## Known limitations",
            "See failing_gates and recommendations.",
        ]
    )


def missing_report_sections(markdown: str) -> list[str]:
    return [section for section in MANDATORY_SECTIONS if section not in markdown]
