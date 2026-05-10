"""Operational harness gate computation."""

from __future__ import annotations

import uuid

from llm_sca_tooling.release.models import OperationalHarnessGateResult
from llm_sca_tooling.schemas.base import JsonObject


def compute_operational_harness_gate(
    *, eval_run_id: str, records: list[JsonObject]
) -> OperationalHarnessGateResult:
    total = max(1, len(records))
    trace_rate = (
        sum(1 for item in records if bool(item.get("trace_complete", True))) / total
    )
    policy_rate = (
        sum(1 for item in records if not bool(item.get("policy_violation", False)))
        / total
    )
    budget_rate = (
        sum(1 for item in records if not bool(item.get("budget_hard_stop", False)))
        / total
    )
    maintainability_rate = (
        sum(1 for item in records if bool(item.get("maintainability_pass", True)))
        / total
    )
    manifest_rate = (
        sum(1 for item in records if bool(item.get("manifest_regression_pass", True)))
        / total
    )
    incident_rate = (
        sum(1 for item in records if not bool(item.get("open_p0_p1", False))) / total
    )
    readiness = all(bool(item.get("readiness_threshold_met", True)) for item in records)
    failing: list[str] = []
    thresholds = {
        "trace_completeness": trace_rate >= 0.90,
        "policy_compliance": policy_rate >= 0.95,
        "budget_reliability": budget_rate >= 0.90,
        "maintainability_oracle": maintainability_rate >= 0.85,
        "manifest_regression": manifest_rate == 1.0,
        "readiness_threshold": readiness,
        "p0_p1_incident_closure": incident_rate == 1.0,
    }
    failing.extend(name for name, passed in thresholds.items() if not passed)
    return OperationalHarnessGateResult(
        gate_id=f"opgate:{uuid.uuid4().hex}",
        eval_run_id=eval_run_id,
        trace_completeness_rate=trace_rate,
        policy_compliance_rate=policy_rate,
        budget_reliability_rate=budget_rate,
        maintainability_oracle_pass_rate=maintainability_rate,
        manifest_regression_pass_rate=manifest_rate,
        readiness_threshold_met=readiness,
        p0_p1_incident_closure_rate=incident_rate,
        gate_passed=not failing,
        failing_gates=failing,
        process_compliance_rate=policy_rate,
        trace_replay_success_rate=trace_rate,
        policy_violation_count=sum(
            1 for item in records if bool(item.get("policy_violation", False))
        ),
        budget_hard_stop_count=sum(
            1 for item in records if bool(item.get("budget_hard_stop", False))
        ),
        incident_recidivism_rate=1.0 - incident_rate,
        cost_per_accepted_verdict=0.0,
    )
