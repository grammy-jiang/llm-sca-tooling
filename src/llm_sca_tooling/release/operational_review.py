"""Full Phase 18 operational-review launcher."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.release.models import OperationalReviewReport

__all__ = ["PROCESS_VERDICTS", "run_operational_review"]

PROCESS_VERDICTS = [
    "process-compliant",
    "process-noncompliant",
    "trace-incomplete",
    "budget-exhausted",
    "needs-readiness-work",
]

_REQUIRED_EVENTS = {"tool_call", "gate_result", "budget_event", "final_verdict"}


def run_operational_review(
    *,
    run_id: str,
    policy: str | None = None,
    task: str | None = None,
    run_events: list[dict[str, Any]] | None = None,
    harness_condition_id: str | None = None,
) -> OperationalReviewReport:
    del policy, task
    events = run_events or []
    event_types = {str(event.get("type", "")) for event in events}
    trace_complete = _REQUIRED_EVENTS.issubset(event_types)
    denied = [
        str(event.get("action", event.get("type", "")))
        for event in events
        if event.get("policy_action") == "deny"
    ]
    approved = [
        str(event.get("action", event.get("type", "")))
        for event in events
        if event.get("policy_action") == "approve"
    ]
    budget_hard_stop = any(event.get("type") == "budget_hard_stop" for event in events)
    policy_violation = any(event.get("type") == "policy_violation" for event in events)
    readiness_work = any(event.get("type") == "readiness_failure" for event in events)
    verdict = _verdict(
        trace_complete=trace_complete,
        budget_hard_stop=budget_hard_stop,
        policy_violation=policy_violation,
        readiness_work=readiness_work,
    )
    return OperationalReviewReport(
        run_id=run_id,
        process_compliance_verdict=verdict,
        trace_completeness="complete" if trace_complete else "missing",
        denied_actions=denied,
        approved_actions=approved,
        budget_behaviour="hard-stop" if budget_hard_stop else "within-budget",
        compaction_loss="not_observed",
        verification_adequacy=(
            "adequate" if "verification_event" in event_types else "not_recorded"
        ),
        maintainability_oracle_results=[
            str(event.get("result"))
            for event in events
            if event.get("type") == "maintainability_oracle"
        ],
        lessons_eligible_for_promotion=[
            str(event.get("lesson_id"))
            for event in events
            if event.get("type") == "lesson_candidate"
            and event.get("review_approved") is True
        ],
        harness_condition_id=harness_condition_id,
    )


def _verdict(
    *,
    trace_complete: bool,
    budget_hard_stop: bool,
    policy_violation: bool,
    readiness_work: bool,
) -> str:
    if not trace_complete:
        return "trace-incomplete"
    if budget_hard_stop:
        return "budget-exhausted"
    if policy_violation:
        return "process-noncompliant"
    if readiness_work:
        return "needs-readiness-work"
    return "process-compliant"
