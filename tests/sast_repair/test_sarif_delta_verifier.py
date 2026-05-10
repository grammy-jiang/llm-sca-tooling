"""Tests for SARIF delta verification."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.sarif_delta_verifier import verify_sarif_delta


def test_delta_success_when_alert_gone() -> None:
    result = verify_sarif_delta(
        alert_id="a1",
        before_alerts=[{"alert_id": "a1", "severity": "high"}],
        after_alerts=[],
    )
    assert result.success is True
    assert result.original_alert_gone is True
    assert result.original_alert_remains is False
    assert result.block_reason is None


def test_delta_blocked_by_new_critical() -> None:
    result = verify_sarif_delta(
        alert_id="a1",
        before_alerts=[{"alert_id": "a1", "severity": "high"}],
        after_alerts=[{"alert_id": "a2", "normalized_severity": "critical"}],
    )
    assert result.success is False
    assert result.block_reason == "new_critical_or_error_alerts"
    assert result.new_critical_or_error_alerts


def test_delta_original_alert_remains() -> None:
    result = verify_sarif_delta(
        alert_id="a1",
        before_alerts=[{"alert_id": "a1", "severity": "high"}],
        after_alerts=[{"alert_id": "a1", "severity": "high"}],
    )
    assert result.original_alert_remains is True
    assert result.block_reason == "original_alert_remains"


def test_delta_severity_regression() -> None:
    result = verify_sarif_delta(
        alert_id="a1",
        before_alerts=[
            {"alert_id": "a1", "severity": "high"},
            {"alert_id": "a3", "severity": "low"},
        ],
        after_alerts=[
            {"alert_id": "a3", "severity": "high"},
        ],
    )
    assert result.severity_regressions
    assert result.severity_regressions[0]["alert_id"] == "a3"


def test_delta_net_alert_delta() -> None:
    result = verify_sarif_delta(
        alert_id="a1",
        before_alerts=[{"alert_id": "a1"}],
        after_alerts=[{"alert_id": "a2"}, {"alert_id": "a3"}],
    )
    assert result.net_alert_delta == 1
