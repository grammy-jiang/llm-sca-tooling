"""SARIF delta verification for SAST repair."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.sast_repair.models import SARIFDeltaVerificationResult


def verify_sarif_delta(
    *,
    alert_id: str,
    before_alerts: list[dict[str, Any]],
    after_alerts: list[dict[str, Any]],
    before_run_id: str = "before",
    after_run_id: str = "after",
) -> SARIFDeltaVerificationResult:
    original_remains = any(
        str(alert.get("alert_id")) == alert_id for alert in after_alerts
    )
    original_gone = not original_remains
    before_keys = {_key(alert) for alert in before_alerts}
    new_alerts = [alert for alert in after_alerts if _key(alert) not in before_keys]
    critical = [
        alert
        for alert in new_alerts
        if str(alert.get("severity", alert.get("level", ""))).lower()
        in {"critical", "error"}
    ]
    block = "original_alert_remains" if original_remains else None
    if critical:
        block = "new_critical_or_error_alert"
    return SARIFDeltaVerificationResult(
        alert_id=alert_id,
        sarif_run_before_id=before_run_id,
        sarif_run_after_id=after_run_id,
        original_alert_gone=original_gone,
        original_alert_remains=original_remains,
        new_alerts=new_alerts,
        new_critical_or_error_alerts=critical,
        severity_regressions=[],
        net_alert_delta=len(after_alerts) - len(before_alerts),
        success=original_gone and not critical,
        block_reason=block,
    )


def _key(alert: dict[str, Any]) -> str:
    return ":".join(
        str(alert.get(field, "")) for field in ("rule_id", "file_path", "line")
    )
