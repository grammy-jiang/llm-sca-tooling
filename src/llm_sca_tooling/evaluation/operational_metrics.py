"""Operational quality metric computation for eval runs."""

from __future__ import annotations

from collections.abc import Iterable

from llm_sca_tooling.evaluation.models import (
    EvalInstanceResult,
    OperationalQualityMetrics,
)

REQUIRED_EVENT_TYPES = {"tool_call", "gate_result", "budget_event", "final_verdict"}


def compute_operational_quality_metrics(
    eval_run_id: str,
    instance_results: Iterable[EvalInstanceResult],
    *,
    readiness_delta: float = 0.0,
) -> OperationalQualityMetrics:
    results = list(instance_results)
    compliant = [_has_required_events(result) for result in results]
    replayable = [bool(result.gate_results) for result in results]
    policy_violations = 0
    budget_stops = 0
    accepted = 0
    token_total = 0
    for result in results:
        token_total += result.token_count
        if result.gate_results and all(gate.passed for gate in result.gate_results):
            accepted += 1
        for event in result.budget_events:
            if (
                event.get("type") == "policy_violation"
                or event.get("policy_action") == "deny"
            ):
                policy_violations += 1
            if event.get("type") == "budget_hard_stop":
                budget_stops += 1
    return OperationalQualityMetrics(
        eval_run_id=eval_run_id,
        process_compliance_rate=_rate(compliant),
        trace_replay_success_rate=_rate(replayable),
        policy_violation_count=policy_violations,
        budget_hard_stop_count=budget_stops,
        incident_recidivism_rate=0.0,
        promotion_precision_placeholder=0.0,
        cost_per_accepted_verdict=(token_total / accepted) if accepted else None,
        readiness_delta=readiness_delta,
    )


def _has_required_events(result: EvalInstanceResult) -> bool:
    event_types = {
        str(event.get("type")) for event in result.budget_events if event.get("type")
    }
    if result.gate_results:
        event_types.add("gate_result")
    return REQUIRED_EVENT_TYPES.issubset(event_types)


def _rate(flags: Iterable[bool]) -> float:
    values = list(flags)
    if not values:
        return 0.0
    return sum(1 for value in values if value) / len(values)
