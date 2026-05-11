"""Four-axis patch audit with deterministic fallback."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import AxisFinding, PatchRiskResult

AXES = ("correctness", "security", "performance", "compatibility")


def run_four_axis_audit(
    *, risk: PatchRiskResult, evidence_ref: str, sampling_supported: bool = False
) -> dict[str, AxisFinding]:
    findings: dict[str, AxisFinding] = {}
    for axis in AXES:
        axis_findings: list[str] = []
        signals = list(risk.active_overrides)
        if axis == "security" and any("sarif" in item for item in signals):
            axis_findings.append("security SARIF override active")
        elif axis == "compatibility" and "breaking-interface-change" in signals:
            axis_findings.append("breaking interface change requires review")
        elif axis == "correctness" and "failing-required-test" in signals:
            axis_findings.append("required test regression blocks merge")
        elif not signals:
            axis_findings.append("no deterministic axis finding")
        findings[axis] = AxisFinding(
            axis=axis,
            findings=axis_findings,
            evidence_refs=[evidence_ref],
            risk_signals=signals,
            confidence="heuristic",
            sampling_used=sampling_supported,
            reviewer_id=f"{axis}-reviewer",
        )
    return findings
