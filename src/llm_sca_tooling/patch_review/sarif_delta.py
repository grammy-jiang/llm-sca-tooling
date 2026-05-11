"""SARIF before/after delta for patch review."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.patch_review.models import SARIFDeltaRecord


def compute_sarif_delta(
    *,
    diff_id: str,
    before: list[dict[str, Any]] | None = None,
    after: list[dict[str, Any]] | None = None,
) -> SARIFDeltaRecord:
    before = before or []
    after = after or []
    before_keys = {_key(alert): alert for alert in before}
    after_keys = {_key(alert): alert for alert in after}
    new = [alert for key, alert in after_keys.items() if key not in before_keys]
    fixed = [alert for key, alert in before_keys.items() if key not in after_keys]
    changed = [
        after_keys[key]
        for key in set(before_keys) & set(after_keys)
        if _severity(before_keys[key]) != _severity(after_keys[key])
    ]
    return SARIFDeltaRecord(
        diff_id=diff_id,
        new_alerts=new,
        fixed_alerts=fixed,
        severity_changed=changed,
        location_changed=[],
        has_new_critical=any(
            _severity(alert) in {"critical", "error"} for alert in new
        ),
        has_new_security=any(_is_security(alert) for alert in new),
    )


def _key(alert: dict[str, Any]) -> str:
    return ":".join(
        str(alert.get(part, "")) for part in ("rule_id", "file_path", "line", "message")
    )


def _severity(alert: dict[str, Any]) -> str:
    return str(alert.get("severity", alert.get("level", ""))).lower()


def _is_security(alert: dict[str, Any]) -> bool:
    haystack = " ".join(str(value).lower() for value in alert.values())
    return any(term in haystack for term in ("cwe", "injection", "taint", "xss"))
