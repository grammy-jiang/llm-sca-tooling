"""Operational-quality metric computation."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.evaluation.models import (
    EvalInstanceResult,
    OperationalQualityMetrics,
)

__all__ = ["compute_operational_metrics"]

REQUIRED_EVENT_TYPES = {"tool_call", "gate_result", "budget_event", "final_verdict"}


def compute_operational_metrics(
    *,
    eval_run_id: str,
    instance_results: list[EvalInstanceResult],
    run_events: list[dict[str, Any]] | None = None,
    previous_readiness_score: float | None = None,
    current_readiness_score: float | None = None,
) -> OperationalQualityMetrics:
    run_events = run_events or []
    grouped: dict[str, set[str]] = {}
    violations = 0
    hard_stops = 0
    for event in run_events:
        instance_id = str(event.get("instance_id", ""))
        event_type = str(event.get("type", ""))
        grouped.setdefault(instance_id, set()).add(event_type)
        if event_type == "policy_violation":
            violations += 1
        if event_type == "budget_hard_stop":
            hard_stops += 1
    compliance_count = sum(
        REQUIRED_EVENT_TYPES.issubset(grouped.get(result.instance_id, set()))
        for result in instance_results
    )
    accepted = sum(
        all(gate.get("passed", False) for gate in result.gate_results)
        for result in instance_results
    )
    tokens = sum(result.token_count for result in instance_results)
    total = len(instance_results) or 1
    readiness_delta = (
        (current_readiness_score or 0.0) - (previous_readiness_score or 0.0)
        if current_readiness_score is not None or previous_readiness_score is not None
        else 0.0
    )
    return OperationalQualityMetrics(
        eval_run_id=eval_run_id,
        process_compliance_rate=compliance_count / total,
        trace_replay_success_rate=1.0 if instance_results else 0.0,
        policy_violation_count=violations,
        budget_hard_stop_count=hard_stops,
        cost_per_accepted_verdict=(tokens / accepted) if accepted else 0.0,
        readiness_delta=readiness_delta,
    )
