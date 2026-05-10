"""Operational-review integration for patch-review."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.patch_review.models import (
    OperationalIntegrationResult,
    ProcessVerdict,
    Recommendation,
    ScopeAuditResult,
)


def integrate_operational(
    *,
    run_id: str | None,
    scope_audit: ScopeAuditResult | None,
    incident_ids: list[str] | None = None,
    policy_violation_count: int = 0,
    budget_hard_stop: bool = False,
) -> OperationalIntegrationResult:
    """Map operational signals into the patch-review recommendation space."""
    incidents = incident_ids or []
    if scope_audit is None:
        verdict = (
            ProcessVerdict.TRACE_INCOMPLETE
            if run_id is None
            else ProcessVerdict.UNKNOWN
        )
        recommendation = Recommendation.REVIEW_REQUIRED
        return OperationalIntegrationResult(
            run_id=run_id,
            process_verdict=verdict,
            incident_count=len(incidents),
            incident_ids=incidents,
            trace_complete=False,
            budget_hard_stop=budget_hard_stop,
            policy_violation_count=policy_violation_count,
            missing_required_events=[],
            operational_recommendation=recommendation,
        )

    verdict = scope_audit.process_verdict
    if (
        verdict == ProcessVerdict.PROCESS_COMPLIANT
        and not incidents
        and not policy_violation_count
    ):
        recommendation = Recommendation.MERGE_SUPPORTING
    elif verdict in {ProcessVerdict.TRACE_INCOMPLETE, ProcessVerdict.BUDGET_EXHAUSTED}:
        recommendation = Recommendation.REVIEW_REQUIRED
    elif verdict == ProcessVerdict.PROCESS_NONCOMPLIANT:
        recommendation = Recommendation.BLOCK
    else:
        recommendation = Recommendation.REVIEW_REQUIRED

    return OperationalIntegrationResult(
        run_id=run_id,
        process_verdict=verdict,
        incident_count=len(incidents),
        incident_ids=incidents,
        trace_complete=scope_audit.trace_complete,
        budget_hard_stop=budget_hard_stop,
        policy_violation_count=policy_violation_count,
        missing_required_events=scope_audit.missing_required_events,
        operational_recommendation=recommendation,
    )


def coerce_recommendation(value: Any) -> Recommendation:
    if isinstance(value, Recommendation):
        return value
    return Recommendation(str(value))
