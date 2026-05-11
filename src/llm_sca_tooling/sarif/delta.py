"""SARIF before/after delta computation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from llm_sca_tooling.sarif.models import (
    AlertChange,
    NormalizedAlert,
    NormalizedSarifRun,
    SarifDelta,
)

__all__ = ["compute_sarif_delta"]


def compute_sarif_delta(
    before: NormalizedSarifRun, after: NormalizedSarifRun
) -> SarifDelta:
    before_by_fp = {alert.fingerprint: alert for alert in before.alerts}
    after_by_fp = {alert.fingerprint: alert for alert in after.alerts}
    unchanged = [
        after_by_fp[fingerprint]
        for fingerprint in sorted(before_by_fp.keys() & after_by_fp.keys())
    ]
    matched_before = {alert.alert_id for alert in unchanged}
    matched_after = {alert.alert_id for alert in unchanged}
    changed: list[AlertChange] = []
    for old in before.alerts:
        if old.alert_id in matched_before:
            continue
        candidate = _fuzzy_match(old, after.alerts, matched_after)
        if candidate:
            changed.append(
                AlertChange(
                    before_alert=old,
                    after_alert=candidate,
                    change_type=_change_type(old, candidate),
                )
            )
            matched_before.add(old.alert_id)
            matched_after.add(candidate.alert_id)
    disappeared = [
        alert for alert in before.alerts if alert.alert_id not in matched_before
    ]
    appeared = [alert for alert in after.alerts if alert.alert_id not in matched_after]
    delta_id = _delta_id(before.run_id, after.run_id, appeared, disappeared, changed)
    return SarifDelta(
        delta_id=delta_id,
        before_run_id=before.run_id,
        after_run_id=after.run_id,
        repo_id=after.repo_id,
        before_snapshot_id=before.snapshot_id,
        after_snapshot_id=after.snapshot_id,
        appeared=appeared,
        disappeared=disappeared,
        unchanged=unchanged,
        changed=changed,
        suppressed_in_before=[alert for alert in before.alerts if alert.suppressed],
        suppressed_in_after=[alert for alert in after.alerts if alert.suppressed],
        computed_ts=datetime.now(UTC).isoformat(),
    )


def _fuzzy_match(
    old: NormalizedAlert, candidates: list[NormalizedAlert], matched_after: set[str]
) -> NormalizedAlert | None:
    for candidate in candidates:
        if candidate.alert_id in matched_after:
            continue
        if old.rule_id != candidate.rule_id or old.file_path != candidate.file_path:
            continue
        old_line = old.start_line or 0
        new_line = candidate.start_line or 0
        if abs(old_line - new_line) <= 5 or old.message != candidate.message:
            return candidate
    return None


def _change_type(old: NormalizedAlert, new: NormalizedAlert) -> str:
    if old.normalized_severity != new.normalized_severity:
        return "severity_changed"
    if old.suppressed != new.suppressed:
        return "suppression_changed"
    if old.message != new.message:
        return "message_changed"
    return "location_shifted"


def _delta_id(
    before_id: str,
    after_id: str,
    appeared: list[NormalizedAlert],
    disappeared: list[NormalizedAlert],
    changed: list[AlertChange],
) -> str:
    payload = "|".join(
        [
            before_id,
            after_id,
            ",".join(sorted(alert.alert_id for alert in appeared)),
            ",".join(sorted(alert.alert_id for alert in disappeared)),
            ",".join(sorted(change.after_alert.alert_id for change in changed)),
        ]
    )
    return f"sarif-delta:{hashlib.sha256(payload.encode()).hexdigest()[:16]}"
