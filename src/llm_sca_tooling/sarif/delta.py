"""SARIF before/after delta computation."""

from __future__ import annotations

from llm_sca_tooling.sarif.models import AlertChange, AlertChangeType, NormalizedAlert, NormalizedSarifRun, SarifDelta
from llm_sca_tooling.storage.ids import stable_hash
from llm_sca_tooling.storage.workspace import _now_ts


class SarifDeltaComputer:
    def compute(self, before: NormalizedSarifRun, after: NormalizedSarifRun) -> SarifDelta:
        before_by_fp = {alert.fingerprint: alert for alert in before.alerts}
        after_by_fp = {alert.fingerprint: alert for alert in after.alerts}
        unchanged = [before_by_fp[fp] for fp in sorted(set(before_by_fp) & set(after_by_fp))]
        matched_before = {alert.alert_id for alert in unchanged}
        matched_after = {after_by_fp[fp].alert_id for fp in set(before_by_fp) & set(after_by_fp)}
        changed: list[AlertChange] = []
        for before_alert in before.alerts:
            if before_alert.alert_id in matched_before:
                continue
            candidate = _find_fuzzy(before_alert, after.alerts, matched_after)
            if candidate is None:
                continue
            change_type = _change_type(before_alert, candidate)
            changed.append(AlertChange(before_alert=before_alert, after_alert=candidate, change_type=change_type))
            matched_before.add(before_alert.alert_id)
            matched_after.add(candidate.alert_id)
        appeared = [alert for alert in after.alerts if alert.alert_id not in matched_after]
        disappeared = [alert for alert in before.alerts if alert.alert_id not in matched_before]
        delta_id = f"sarif-delta:{stable_hash(before.run_id + '|' + after.run_id, length=20)}"
        return SarifDelta(
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
            delta_id=delta_id,
            computed_ts=_now_ts(),
        )


def compute_sarif_delta(before: NormalizedSarifRun, after: NormalizedSarifRun) -> SarifDelta:
    return SarifDeltaComputer().compute(before, after)


def _find_fuzzy(before: NormalizedAlert, after_alerts: list[NormalizedAlert], matched_after: set[str]) -> NormalizedAlert | None:
    for after in after_alerts:
        if after.alert_id in matched_after:
            continue
        if before.rule_id != after.rule_id or before.file_path != after.file_path:
            continue
        if before.start_line and after.start_line and abs(before.start_line - after.start_line) <= 5:
            return after
        if before.message != after.message or before.normalized_severity != after.normalized_severity or before.suppressed != after.suppressed:
            return after
    return None


def _change_type(before: NormalizedAlert, after: NormalizedAlert) -> AlertChangeType:
    if before.suppressed != after.suppressed:
        return AlertChangeType.SUPPRESSION_CHANGED
    if before.normalized_severity != after.normalized_severity:
        return AlertChangeType.SEVERITY_CHANGED
    if before.message != after.message:
        return AlertChangeType.MESSAGE_CHANGED
    return AlertChangeType.LOCATION_SHIFTED

