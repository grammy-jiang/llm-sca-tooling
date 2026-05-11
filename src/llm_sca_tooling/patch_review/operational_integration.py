"""Operational-review integration."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import (
    OperationalIntegrationResult,
    PolicyAction,
    ScopeAuditResult,
)


def integrate_operational_result(
    scope: ScopeAuditResult,
) -> OperationalIntegrationResult:
    action = (
        PolicyAction.merge_supporting
        if scope.process_verdict == "process-compliant"
        else PolicyAction.review_required
    )
    if scope.out_of_scope_writes or scope.process_verdict == "process-noncompliant":
        action = PolicyAction.block
    return OperationalIntegrationResult(
        run_id=scope.run_id,
        process_verdict=scope.process_verdict,
        trace_complete=scope.trace_complete,
        budget_hard_stop=scope.process_verdict == "budget-exhausted",
        policy_violation_count=len(scope.out_of_scope_writes),
        missing_required_events=scope.missing_required_events,
        operational_recommendation=action,
    )
