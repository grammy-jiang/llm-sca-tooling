"""SARIF-delta wrapper for patch-review.

Reuses the Phase 6 ``compute_sarif_delta`` utility when normalized SARIF
runs are available; otherwise produces an ``available=False`` placeholder
that downstream gates treat as ``unknown`` (not ``clean``).
"""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.patch_review.models import SARIFDelta, SARIFDeltaAlert

_CRITICAL_SEVERITIES = {"critical", "error", "high"}
_SECURITY_RULE_HINTS = (
    "taint",
    "injection",
    "sqli",
    "xss",
    "ssrf",
    "deserial",
    "rce",
    "auth",
    "csrf",
    "redos",
    "path-traversal",
    "command-injection",
)


def _alert_from_dict(payload: dict[str, Any]) -> SARIFDeltaAlert:
    return SARIFDeltaAlert(
        alert_id=str(payload.get("alert_id") or payload.get("fingerprint") or "alert"),
        rule_id=payload.get("rule_id"),
        severity=str(payload.get("severity")) if payload.get("severity") else None,
        cwe=payload.get("cwe"),
        rule_family=payload.get("rule_family"),
        file_path=payload.get("file_path"),
    )


def _is_security(alert: SARIFDeltaAlert) -> bool:
    rule = (alert.rule_id or "").lower()
    family = (alert.rule_family or "").lower()
    if alert.cwe:
        return True
    return any(hint in rule for hint in _SECURITY_RULE_HINTS) or any(
        hint in family for hint in _SECURITY_RULE_HINTS
    )


def _is_critical(alert: SARIFDeltaAlert) -> bool:
    sev = (alert.severity or "").lower()
    return sev in _CRITICAL_SEVERITIES


def build_sarif_delta(
    diff_id: str,
    *,
    appeared: list[dict[str, Any]] | None = None,
    disappeared: list[dict[str, Any]] | None = None,
    severity_changed: list[dict[str, Any]] | None = None,
    location_changed: list[dict[str, Any]] | None = None,
    before_run_id: str | None = None,
    after_run_id: str | None = None,
    available: bool = True,
) -> SARIFDelta:
    """Build a :class:`SARIFDelta` from pre-computed alert lists.

    The Phase 6 ``compute_sarif_delta`` utility produces a richer
    structure; ``build_sarif_delta`` accepts the simplified-dict form so
    the patch-review pipeline can plug into other delta sources too.
    """
    appeared_alerts = [_alert_from_dict(a) for a in (appeared or [])]
    disappeared_alerts = [_alert_from_dict(a) for a in (disappeared or [])]
    severity_alerts = [_alert_from_dict(a) for a in (severity_changed or [])]
    location_alerts = [_alert_from_dict(a) for a in (location_changed or [])]
    new_critical = sum(1 for a in appeared_alerts if _is_critical(a))
    new_security = sum(1 for a in appeared_alerts if _is_security(a))
    diagnostics = []
    if not available:
        diagnostics.append({"code": "sarif_unavailable"})
    return SARIFDelta(
        diff_id=diff_id,
        before_run_id=before_run_id,
        after_run_id=after_run_id,
        appeared=appeared_alerts,
        disappeared=disappeared_alerts,
        severity_changed=severity_alerts,
        location_changed=location_alerts,
        new_critical_count=new_critical,
        new_security_count=new_security,
        available=available,
        diagnostics=diagnostics,
    )


def empty_sarif_delta(diff_id: str) -> SARIFDelta:
    return build_sarif_delta(diff_id, available=False)
