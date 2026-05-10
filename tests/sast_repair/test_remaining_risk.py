"""Tests for remaining-risk note generation."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.models import (
    BuildTestResult,
    PredicateMetadata,
    RiskLevel,
    SARIFDeltaVerificationResult,
)
from llm_sca_tooling.sast_repair.remaining_risk import (
    generate_remaining_risk,
    is_vulnerability_class,
)


def _delta(success: bool = True) -> SARIFDeltaVerificationResult:
    return SARIFDeltaVerificationResult(
        alert_id="a1",
        original_alert_gone=success,
        original_alert_remains=not success,
        success=success,
    )


def _build(passed: bool = True) -> BuildTestResult:
    return BuildTestResult(
        alert_id="a1",
        build_status="ok",
        test_run_status="passed" if passed else "failed",
    )


def test_is_vulnerability_class_by_family() -> None:
    meta = PredicateMetadata(rule_id="r", rule_family="injection")
    assert is_vulnerability_class(meta) is True


def test_is_vulnerability_class_by_severity() -> None:
    meta = PredicateMetadata(rule_id="r", severity="high")
    assert is_vulnerability_class(meta) is True


def test_is_vulnerability_class_false() -> None:
    meta = PredicateMetadata(rule_id="r", rule_family="other", severity="low")
    assert is_vulnerability_class(meta) is False


def test_generate_remaining_risk_high_for_vuln_no_poc() -> None:
    notes = generate_remaining_risk(
        alert_id="a1",
        metadata=PredicateMetadata(rule_id="r", rule_family="injection"),
        sarif_delta=_delta(),
        build_test=_build(),
        poc_plus_available=False,
        graph_dataflow_complete=True,
    )
    assert any(n.risk_level is RiskLevel.HIGH for n in notes)


def test_generate_remaining_risk_medium_dataflow_partial() -> None:
    notes = generate_remaining_risk(
        alert_id="a1",
        metadata=PredicateMetadata(rule_id="r", rule_family="injection"),
        sarif_delta=_delta(),
        build_test=_build(),
        poc_plus_available=True,
        graph_dataflow_complete=False,
    )
    assert any(n.risk_level is RiskLevel.MEDIUM for n in notes)


def test_generate_remaining_risk_only_sarif() -> None:
    notes = generate_remaining_risk(
        alert_id="a1",
        metadata=PredicateMetadata(rule_id="r", rule_family="other"),
        sarif_delta=_delta(),
        build_test=_build(passed=False),
        poc_plus_available=False,
        graph_dataflow_complete=True,
    )
    assert any(n.risk_level is RiskLevel.MEDIUM for n in notes)


def test_generate_remaining_risk_none_when_full_verification() -> None:
    notes = generate_remaining_risk(
        alert_id="a1",
        metadata=PredicateMetadata(rule_id="r", rule_family="other"),
        sarif_delta=_delta(),
        build_test=_build(),
        poc_plus_available=True,
        graph_dataflow_complete=True,
    )
    assert len(notes) == 1
    assert notes[0].risk_level is RiskLevel.NONE
