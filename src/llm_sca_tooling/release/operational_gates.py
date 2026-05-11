"""Operational harness gate runner."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.release.models import OperationalHarnessGateResult

__all__ = ["OperationalHarnessGateRunner", "compute_operational_harness_gate"]


class OperationalHarnessGateRunner:
    """Compute Phase 18 operational gates from stored run-record summaries."""

    def run(
        self,
        *,
        eval_run_id: str,
        run_records: list[dict[str, Any]],
        readiness_threshold_met: bool = True,
    ) -> OperationalHarnessGateResult:
        return compute_operational_harness_gate(
            eval_run_id=eval_run_id,
            run_records=run_records,
            readiness_threshold_met=readiness_threshold_met,
        )


def compute_operational_harness_gate(
    *,
    eval_run_id: str,
    run_records: list[dict[str, Any]],
    readiness_threshold_met: bool = True,
) -> OperationalHarnessGateResult:
    trace_rate = _rate(run_records, "trace_complete")
    policy_rate = _rate(run_records, "policy_compliant")
    budget_rate = _rate(run_records, "budget_reliable")
    maintainability_rate = _rate(run_records, "maintainability_oracle_passed")
    manifest_rate = _rate(run_records, "manifest_regression_passed")
    incident_rate = _incident_closure_rate(run_records)
    policy_violations = sum(
        int(record.get("policy_violation_count", 0)) for record in run_records
    )
    budget_hard_stops = sum(
        int(record.get("budget_hard_stop_count", 0)) for record in run_records
    )
    accepted = sum(1 for record in run_records if record.get("accepted_verdict", True))
    token_total = sum(float(record.get("token_count", 0.0)) for record in run_records)
    failing = _failing_gates(
        trace_rate=trace_rate,
        policy_rate=policy_rate,
        budget_rate=budget_rate,
        maintainability_rate=maintainability_rate,
        manifest_rate=manifest_rate,
        readiness_threshold_met=readiness_threshold_met,
        incident_rate=incident_rate,
    )
    return OperationalHarnessGateResult(
        eval_run_id=eval_run_id,
        trace_completeness_rate=trace_rate,
        policy_compliance_rate=policy_rate,
        budget_reliability_rate=budget_rate,
        maintainability_oracle_pass_rate=maintainability_rate,
        manifest_regression_pass_rate=manifest_rate,
        readiness_threshold_met=readiness_threshold_met,
        p0_p1_incident_closure_rate=incident_rate,
        trace_replay_success_rate=_rate(run_records, "trace_replay_success"),
        policy_violation_count=policy_violations,
        budget_hard_stop_count=budget_hard_stops,
        incident_recidivism_rate=_incident_recidivism_rate(run_records),
        cost_per_accepted_verdict=token_total / accepted if accepted else 0.0,
        gate_passed=not failing,
        failing_gates=failing,
    )


def _rate(records: list[dict[str, Any]], key: str) -> float:
    if not records:
        return 0.0
    return sum(bool(record.get(key, False)) for record in records) / len(records)


def _incident_closure_rate(records: list[dict[str, Any]]) -> float:
    incidents = [
        incident
        for incident in _incident_dicts(records)
        if incident.get("severity") in {"P0", "P1"}
    ]
    if not incidents:
        return 1.0
    closed = sum(1 for incident in incidents if incident.get("status") == "closed")
    return float(closed) / len(incidents)


def _incident_recidivism_rate(records: list[dict[str, Any]]) -> float:
    incidents = _incident_dicts(records)
    if not incidents:
        return 0.0
    repeats = sum(bool(incident.get("recurring", False)) for incident in incidents)
    return repeats / len(incidents)


def _incident_dicts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    incidents: list[dict[str, Any]] = []
    for record in records:
        raw_incidents = record.get("incidents", [])
        if not isinstance(raw_incidents, list):
            continue
        incidents.extend(
            dict(incident) for incident in raw_incidents if isinstance(incident, dict)
        )
    return incidents


def _failing_gates(
    *,
    trace_rate: float,
    policy_rate: float,
    budget_rate: float,
    maintainability_rate: float,
    manifest_rate: float,
    readiness_threshold_met: bool,
    incident_rate: float,
) -> list[str]:
    failing: list[str] = []
    if trace_rate < 0.90:
        failing.append("trace_completeness")
    if policy_rate < 0.95:
        failing.append("policy_compliance")
    if budget_rate < 0.90:
        failing.append("budget_reliability")
    if maintainability_rate < 0.85:
        failing.append("maintainability_oracle")
    if manifest_rate < 1.0:
        failing.append("manifest_regression")
    if not readiness_threshold_met:
        failing.append("readiness_threshold")
    if incident_rate < 1.0:
        failing.append("p0_p1_incident_closure")
    return failing
