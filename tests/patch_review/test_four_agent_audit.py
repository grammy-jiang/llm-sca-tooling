"""Tests for sampling_integration and four_agent_audit."""

from __future__ import annotations

from llm_sca_tooling.patch_review.diff_parser import parse_unified_diff
from llm_sca_tooling.patch_review.four_agent_audit import run_four_agent_audit
from llm_sca_tooling.patch_review.interface_compat import check_interface_compatibility
from llm_sca_tooling.patch_review.models import AuditAxis
from llm_sca_tooling.patch_review.sampling_integration import (
    FallbackSamplingClient,
    build_axis_payload,
)
from llm_sca_tooling.patch_review.sarif_delta import build_sarif_delta


def test_fallback_emits_all_axes(safe_diff: str) -> None:
    diff = parse_unified_diff(safe_diff)
    findings = run_four_agent_audit(diff)
    assert set(findings) == set(AuditAxis)
    for f in findings.values():
        assert not f.sampling_used


def test_fallback_security_axis_flags_critical(safe_diff: str) -> None:
    diff = parse_unified_diff(safe_diff)
    sarif = build_sarif_delta(
        diff.diff_id,
        appeared=[{"alert_id": "a", "severity": "critical", "rule_id": "py/x"}],
    )
    findings = run_four_agent_audit(diff, sarif_delta=sarif)
    assert "new_critical_alert" in findings[AuditAxis.SECURITY].risk_signals


def test_fallback_compatibility_breaking(safe_diff: str) -> None:
    diff = parse_unified_diff(safe_diff)
    iface = check_interface_compatibility(
        diff, interface_records=[{"operation": "/x", "change": "removed"}]
    )
    findings = run_four_agent_audit(diff, interface_compat=iface)
    assert "breaking_interface_change" in findings[AuditAxis.COMPATIBILITY].risk_signals


def test_fallback_correctness_and_performance() -> None:
    diff = parse_unified_diff(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1 +1,3 @@\n base\n+raise ValueError\n+for i in r: pass\n"
    )
    findings = run_four_agent_audit(diff)
    assert "new_exception_path" in findings[AuditAxis.CORRECTNESS].risk_signals
    assert "new_loop" in findings[AuditAxis.PERFORMANCE].risk_signals


def test_axis_payload_shape(safe_diff: str) -> None:
    diff = parse_unified_diff(safe_diff)
    sarif = build_sarif_delta(diff.diff_id)
    payload = build_axis_payload(diff, sarif, ["op"], evidence_refs=["e1"])
    assert payload["evidence_refs"] == ["e1"]
    assert payload["breaking_operations"] == ["op"]


def test_sampling_client_path(safe_diff: str) -> None:
    class FakeSampling:
        available = True

        def create_message(self, *, axis, payload):
            return (
                FallbackSamplingClient()
                .create_message(axis=axis, payload=payload)
                .model_copy(update={"sampling_used": True, "reviewer_id": "fake"})
            )

    diff = parse_unified_diff(safe_diff)
    findings = run_four_agent_audit(diff, sampling_client=FakeSampling())
    assert all(f.sampling_used for f in findings.values())
