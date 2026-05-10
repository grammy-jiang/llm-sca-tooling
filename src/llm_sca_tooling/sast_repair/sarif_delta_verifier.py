"""SARIF delta verification gate."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.sast_repair.models import SARIFDeltaVerificationResult

_HIGH_SEVERITIES = {"critical", "high", "error"}
_RANK = {
    "informational": 0,
    "low": 1,
    "medium": 2,
    "warning": 2,
    "high": 3,
    "error": 3,
    "critical": 4,
}


def _alert_id(alert: dict[str, Any]) -> str:
    return str(alert.get("alert_id") or alert.get("fingerprint") or "")


def verify_sarif_delta(
    *,
    alert_id: str,
    before_alerts: list[dict[str, Any]],
    after_alerts: list[dict[str, Any]],
    before_run_id: str | None = None,
    after_run_id: str | None = None,
) -> SARIFDeltaVerificationResult:
    """Compute the SARIF delta verification result.

    Success requires the original alert to be gone AND no new
    critical/high/error alerts.
    """
    before_ids = {_alert_id(a) for a in before_alerts if _alert_id(a)}
    after_ids = {_alert_id(a) for a in after_alerts if _alert_id(a)}
    original_remains = alert_id in after_ids
    original_gone = alert_id in before_ids and alert_id not in after_ids

    new_alerts = [a for a in after_alerts if _alert_id(a) not in before_ids]
    new_high = [
        a
        for a in new_alerts
        if str(a.get("normalized_severity") or a.get("severity") or "").lower()
        in _HIGH_SEVERITIES
    ]

    severity_regressions: list[dict[str, Any]] = []
    before_by_id = {_alert_id(a): a for a in before_alerts if _alert_id(a)}
    for after in after_alerts:
        aid = _alert_id(after)
        if aid in before_by_id:
            before = before_by_id[aid]
            before_sev = str(
                before.get("normalized_severity") or before.get("severity") or ""
            ).lower()
            after_sev = str(
                after.get("normalized_severity") or after.get("severity") or ""
            ).lower()
            if _RANK.get(after_sev, 0) > _RANK.get(before_sev, 0):
                severity_regressions.append(
                    {
                        "alert_id": aid,
                        "before": before_sev,
                        "after": after_sev,
                    }
                )

    block_reason: str | None = None
    if original_remains:
        block_reason = "original_alert_remains"
    elif new_high:
        block_reason = "new_critical_or_error_alerts"

    success = original_gone and not new_high and not original_remains

    return SARIFDeltaVerificationResult(
        alert_id=alert_id,
        sarif_run_before_id=before_run_id,
        sarif_run_after_id=after_run_id,
        original_alert_gone=original_gone,
        original_alert_remains=original_remains,
        new_alerts=new_alerts,
        new_critical_or_error_alerts=new_high,
        severity_regressions=severity_regressions,
        net_alert_delta=len(after_alerts) - len(before_alerts),
        success=success,
        block_reason=block_reason,
    )


__all__ = ["verify_sarif_delta"]
