"""Anomaly detector for run records.

Detects patterns that indicate workflow problems: repeated tool calls,
repeated failing checks with no code change, context growth without new
evidence, denied-operation storms, budget exhaustion, stale-index evidence,
out-of-scope writes, and cumulative-risk patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["AnomalyFinding", "AnomalyReport", "detect_run_anomalies"]

# Thresholds
_REPEATED_CALL_THRESHOLD = 5
_DENIAL_STORM_THRESHOLD = 3
_CONTEXT_GROWTH_THRESHOLD = 5


@dataclass
class AnomalyFinding:
    kind: str  # repeated_tool | denial_storm | budget_exhaustion | stale_index |
    #            out_of_scope_write | context_growth | repeated_failing | cumulative_risk
    severity: str  # warning | error
    description: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class AnomalyReport:
    run_id: str
    findings: list[AnomalyFinding] = field(default_factory=list)

    @property
    def has_anomalies(self) -> bool:
        return bool(self.findings)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")


def detect_run_anomalies(
    run_id: str,
    events: list[dict[str, Any]],
) -> AnomalyReport:
    """Analyse *events* for a run and return an AnomalyReport.

    Args:
        run_id: The run identifier to include in the report.
        events: Ordered list of run-event dicts (each must have ``type``,
                ``stage``, and optionally ``policy_action``, ``token_count``).
    """
    report = AnomalyReport(run_id=run_id)

    _check_repeated_tool_calls(events, report)
    _check_denial_storm(events, report)
    _check_budget_exhaustion(events, report)
    _check_stale_index(events, report)
    _check_out_of_scope_writes(events, report)
    _check_context_growth_without_evidence(events, report)
    _check_repeated_failing_gates(events, report)
    _check_cumulative_risk(report)

    return report


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_repeated_tool_calls(
    events: list[dict[str, Any]], report: AnomalyReport
) -> None:
    """Detect the same tool call type appearing ≥5 times with identical stage."""
    counts: dict[tuple[str, str], list[str]] = {}
    for evt in events:
        key = (str(evt.get("type", "")), str(evt.get("stage", "")))
        counts.setdefault(key, []).append(str(evt.get("event_id", "")))

    for (etype, stage), ids in counts.items():
        if len(ids) >= _REPEATED_CALL_THRESHOLD:
            report.findings.append(
                AnomalyFinding(
                    kind="repeated_tool",
                    severity="warning",
                    description=(
                        f"Event type {etype!r} repeated {len(ids)}x at stage {stage!r}"
                    ),
                    evidence=ids[:5],
                )
            )


def _check_denial_storm(events: list[dict[str, Any]], report: AnomalyReport) -> None:
    """Detect ≥3 consecutive policy denials (permission-denial storm)."""
    consecutive = 0
    storm_ids: list[str] = []
    for evt in events:
        if evt.get("policy_action") == "deny":
            consecutive += 1
            storm_ids.append(str(evt.get("event_id", "")))
        else:
            consecutive = 0
            storm_ids = []
        if consecutive >= _DENIAL_STORM_THRESHOLD:
            report.findings.append(
                AnomalyFinding(
                    kind="denial_storm",
                    severity="error",
                    description=(
                        f"Permission-denial storm: {consecutive} consecutive denials"
                    ),
                    evidence=storm_ids[:5],
                )
            )
            # Reset to avoid duplicate findings for the same storm
            consecutive = 0
            storm_ids = []


def _check_budget_exhaustion(
    events: list[dict[str, Any]], report: AnomalyReport
) -> None:
    """Detect budget_warning or budget_hard_stop events."""
    for evt in events:
        etype = str(evt.get("type", ""))
        if etype in ("budget_warning", "budget_hard_stop"):
            severity = "error" if etype == "budget_hard_stop" else "warning"
            report.findings.append(
                AnomalyFinding(
                    kind="budget_exhaustion",
                    severity=severity,
                    description=f"Budget event: {etype}",
                    evidence=[str(evt.get("event_id", ""))],
                )
            )


def _check_stale_index(events: list[dict[str, Any]], report: AnomalyReport) -> None:
    """Detect stale_index_evidence or GIT_DIRTY_WORKTREE events."""
    for evt in events:
        etype = str(evt.get("type", ""))
        if "stale_index" in etype or "dirty_worktree" in etype.lower():
            report.findings.append(
                AnomalyFinding(
                    kind="stale_index",
                    severity="warning",
                    description=f"Stale index signal detected: {etype}",
                    evidence=[str(evt.get("event_id", ""))],
                )
            )


def _check_out_of_scope_writes(
    events: list[dict[str, Any]], report: AnomalyReport
) -> None:
    """Detect out_of_scope_write events."""
    for evt in events:
        etype = str(evt.get("type", ""))
        if "out_of_scope" in etype or "out-of-scope" in etype:
            report.findings.append(
                AnomalyFinding(
                    kind="out_of_scope_write",
                    severity="error",
                    description=f"Out-of-scope write attempt: {etype}",
                    evidence=[str(evt.get("event_id", ""))],
                )
            )


def _check_context_growth_without_evidence(
    events: list[dict[str, Any]], report: AnomalyReport
) -> None:
    """Detect context_load events without intervening evidence events."""
    context_loads = 0
    evidence_events = 0
    load_ids: list[str] = []
    for evt in events:
        etype = str(evt.get("type", ""))
        if etype == "context_load":
            context_loads += 1
            load_ids.append(str(evt.get("event_id", "")))
        elif etype in ("tool_result", "graph_query", "sarif_result"):
            evidence_events += 1

    if context_loads >= _CONTEXT_GROWTH_THRESHOLD and evidence_events == 0:
        report.findings.append(
            AnomalyFinding(
                kind="context_growth",
                severity="warning",
                description=(
                    f"Context loaded {context_loads}x without any evidence events"
                ),
                evidence=load_ids[:5],
            )
        )


def _check_repeated_failing_gates(
    events: list[dict[str, Any]], report: AnomalyReport
) -> None:
    """Detect a gate event failing multiple times without a code-change event."""
    gate_failures: dict[str, int] = {}
    code_changed = False
    for evt in events:
        etype = str(evt.get("type", ""))
        if "code_change" in etype or "diff_snapshot" in etype:
            code_changed = True
            gate_failures.clear()
        elif etype == "gate_failed":
            gate_id = str(evt.get("stage", "unknown"))
            gate_failures[gate_id] = gate_failures.get(gate_id, 0) + 1

    if not code_changed:
        for gate_id, count in gate_failures.items():
            if count >= 3:
                report.findings.append(
                    AnomalyFinding(
                        kind="repeated_failing",
                        severity="warning",
                        description=(
                            f"Gate {gate_id!r} failed {count}x with no code change"
                        ),
                    )
                )


def _check_cumulative_risk(report: AnomalyReport) -> None:
    """Flag runs where individually harmless findings combine into a risk pattern."""
    if report.error_count >= 2:
        kinds = {f.kind for f in report.findings if f.severity == "error"}
        if len(kinds) >= 2:
            report.findings.append(
                AnomalyFinding(
                    kind="cumulative_risk",
                    severity="error",
                    description=(
                        f"Cumulative risk: {len(kinds)} distinct error-severity anomaly"
                        f" types ({', '.join(sorted(kinds))})"
                    ),
                )
            )
