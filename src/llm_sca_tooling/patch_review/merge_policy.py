"""Patch-review recommendation policy."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import (
    OperationalIntegrationResult,
    PatchRiskResult,
    PolicyAction,
)


def recommend_merge(
    *, risk: PatchRiskResult, operational: OperationalIntegrationResult
) -> PolicyAction:
    if (
        risk.policy_action == PolicyAction.block
        or operational.operational_recommendation == PolicyAction.block
    ):
        return PolicyAction.block
    if (
        risk.policy_action == PolicyAction.merge_supporting
        and operational.operational_recommendation == PolicyAction.merge_supporting
    ):
        return PolicyAction.merge_supporting
    if risk.policy_action == PolicyAction.unknown:
        return PolicyAction.unknown
    return PolicyAction.review_required
