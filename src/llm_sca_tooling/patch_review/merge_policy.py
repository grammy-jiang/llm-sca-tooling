"""Merge/block recommendation policy."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import (
    MaintainabilityGateResult,
    OperationalIntegrationResult,
    PatchRiskResult,
    PolicyActionValue,
    Recommendation,
    SARIFDelta,
    ScopeAuditResult,
)


def derive_recommendation(
    risk_result: PatchRiskResult,
    *,
    operational: OperationalIntegrationResult | None = None,
    maintainability: MaintainabilityGateResult | None = None,
    sarif_delta: SARIFDelta | None = None,
    scope_audit: ScopeAuditResult | None = None,
) -> Recommendation:
    """Combine risk classifier output with operational/process verdicts.

    Deterministic block conditions always win over advisory signals.
    """
    if risk_result.policy_action == PolicyActionValue.BLOCK:
        return Recommendation.BLOCK
    if (
        sarif_delta
        and sarif_delta.new_critical_count + sarif_delta.new_security_count > 0
    ):
        return Recommendation.BLOCK
    if scope_audit and scope_audit.out_of_scope_writes:
        return Recommendation.BLOCK
    if maintainability and maintainability.block_merge:
        return Recommendation.REVIEW_REQUIRED
    if operational is not None:
        if operational.operational_recommendation == Recommendation.BLOCK:
            return Recommendation.BLOCK
        if operational.operational_recommendation == Recommendation.REVIEW_REQUIRED:
            return Recommendation.REVIEW_REQUIRED
    if risk_result.policy_action == PolicyActionValue.REVIEW_REQUIRED:
        return Recommendation.REVIEW_REQUIRED
    if risk_result.policy_action == PolicyActionValue.UNKNOWN:
        return Recommendation.UNKNOWN
    return Recommendation.MERGE_SUPPORTING
