"""MCP Sampling integration with deterministic fallback for patch audit."""

from __future__ import annotations

from typing import Any, Protocol

from llm_sca_tooling.patch_review.models import (
    AuditAxis,
    AxisFinding,
    ConfidenceLevel,
    DiffRecord,
    SARIFDelta,
)


class SamplingClient(Protocol):
    """Minimal protocol for the MCP Sampling client."""

    available: bool

    def create_message(
        self, *, axis: AuditAxis, payload: dict[str, Any]
    ) -> AxisFinding:
        """Send a `sampling/createMessage` request and return a typed finding."""


class FallbackSamplingClient:
    """Local deterministic fallback that mimics the Sampling response contract.

    The fallback path computes risk signals from the diff and SARIF delta only;
    it never invents evidence the deterministic gates have not surfaced.
    """

    available = False

    def create_message(
        self, *, axis: AuditAxis, payload: dict[str, Any]
    ) -> AxisFinding:
        diff_text = str(payload.get("diff_text", ""))
        new_critical = int(payload.get("new_critical_count", 0))
        new_security = int(payload.get("new_security_count", 0))
        breaking = list(payload.get("breaking_operations", []))
        risk_signals: list[str] = []
        findings: list[str] = []
        if axis == AuditAxis.SECURITY:
            if new_critical:
                risk_signals.append("new_critical_alert")
                findings.append("New critical SARIF alert detected after patch.")
            if new_security:
                risk_signals.append("new_security_alert")
                findings.append("New security-class alert detected after patch.")
            if not findings:
                findings.append(
                    "No security-class alerts detected by deterministic gates."
                )
        elif axis == AuditAxis.CORRECTNESS:
            if "raise " in diff_text:
                risk_signals.append("new_exception_path")
                findings.append("Patch introduces a new raise statement.")
            else:
                findings.append("No correctness signal beyond deterministic gates.")
        elif axis == AuditAxis.PERFORMANCE:
            if "for " in diff_text or "while " in diff_text:
                risk_signals.append("new_loop")
                findings.append("Patch introduces a new loop construct.")
            else:
                findings.append("No performance hotspot signal detected.")
        elif axis == AuditAxis.COMPATIBILITY:
            if breaking:
                risk_signals.append("breaking_interface_change")
                findings.append(
                    f"Breaking interface operations detected: {sorted(breaking)}"
                )
            else:
                findings.append("No interface-compatibility risk detected.")
        return AxisFinding(
            axis=axis,
            findings=findings,
            evidence_refs=list(payload.get("evidence_refs", [])),
            risk_signals=risk_signals,
            confidence=ConfidenceLevel.HEURISTIC,
            sampling_used=False,
            reviewer_id="fallback-local",
        )


def build_axis_payload(
    diff: DiffRecord,
    sarif_delta: SARIFDelta | None,
    breaking_operations: list[str],
    *,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "diff_text": diff.diff_text,
        "new_critical_count": sarif_delta.new_critical_count if sarif_delta else 0,
        "new_security_count": sarif_delta.new_security_count if sarif_delta else 0,
        "breaking_operations": breaking_operations,
        "evidence_refs": evidence_refs or [],
    }
