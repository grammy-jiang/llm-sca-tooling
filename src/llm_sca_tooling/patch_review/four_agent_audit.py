"""Four-agent patch audit (correctness, security, performance, compatibility)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from llm_sca_tooling.patch_review.models import (
    AuditAxis,
    AxisFinding,
    DiffRecord,
    InterfaceCompatibilityResult,
    SARIFDelta,
)
from llm_sca_tooling.patch_review.sampling_integration import (
    FallbackSamplingClient,
    SamplingClient,
    build_axis_payload,
)

_AXES = (
    AuditAxis.CORRECTNESS,
    AuditAxis.SECURITY,
    AuditAxis.PERFORMANCE,
    AuditAxis.COMPATIBILITY,
)


def _run_axis(
    client: SamplingClient, axis: AuditAxis, payload: dict[str, Any]
) -> tuple[AuditAxis, AxisFinding]:
    finding = client.create_message(axis=axis, payload=payload)
    if finding.axis != axis:
        finding = finding.model_copy(update={"axis": axis})
    return axis, finding


def run_four_agent_audit(
    diff: DiffRecord,
    *,
    sarif_delta: SARIFDelta | None = None,
    interface_compat: InterfaceCompatibilityResult | None = None,
    sampling_client: SamplingClient | None = None,
    evidence_refs: list[str] | None = None,
) -> dict[AuditAxis, AxisFinding]:
    """Launch the four review axes in parallel via MCP Sampling, with fallback.

    When ``sampling_client`` is None or its ``available`` attribute is False,
    a deterministic local fallback path is used. Both paths emit
    :class:`AxisFinding` records with the same shape so the report layer is
    agnostic to the source.
    """
    breaking_ops: list[str] = []
    if interface_compat is not None:
        breaking_ops = [
            str(item.get("operation", ""))
            for item in interface_compat.breaking_changes
            if item.get("operation")
        ]
    payload = build_axis_payload(
        diff, sarif_delta, breaking_ops, evidence_refs=evidence_refs
    )
    client = sampling_client or FallbackSamplingClient()
    findings: dict[AuditAxis, AxisFinding] = {}
    with ThreadPoolExecutor(max_workers=len(_AXES)) as pool:
        futures = {
            pool.submit(_run_axis, client, axis, payload): axis for axis in _AXES
        }
        for future in as_completed(futures):
            axis, finding = future.result()
            findings[axis] = finding
    return findings
