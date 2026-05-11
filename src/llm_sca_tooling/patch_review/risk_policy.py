"""Deterministic Phase 11 risk policy."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import (
    InterfaceCompatibilityResult,
    MaintainabilityGateResult,
    PatchRiskFeatureVector,
    PatchRiskResult,
    PolicyAction,
    RiskClass,
    SARIFDeltaRecord,
    ScopeAuditResult,
    TestDeltaRecord,
)


def apply_deterministic_policy(
    *,
    feature_vector: PatchRiskFeatureVector,
    sarif_delta: SARIFDeltaRecord,
    test_delta: TestDeltaRecord,
    interface: InterfaceCompatibilityResult,
    scope: ScopeAuditResult,
    maintainability: MaintainabilityGateResult,
) -> PatchRiskResult:
    overrides: list[str] = []
    risk = RiskClass.unknown
    action = PolicyAction.unknown
    if sarif_delta.has_new_critical or sarif_delta.has_new_security:
        overrides.append("new-security-sarif-alert")
        risk = RiskClass.vulnerability_introducing
        action = PolicyAction.block
    elif test_delta.newly_failing:
        overrides.append("failing-required-test")
        risk = RiskClass.correct_but_overfit
        action = PolicyAction.block
    elif test_delta.poc_plus_result == "failed":
        overrides.append("poc-plus-failed")
        risk = RiskClass.vulnerable
        action = PolicyAction.block
    elif scope.out_of_scope_writes:
        overrides.append("out-of-scope-write")
        risk = RiskClass.unknown
        action = PolicyAction.block
    elif scope.process_verdict in {
        "trace-incomplete",
        "budget-exhausted",
        "process-noncompliant",
    }:
        overrides.append(scope.process_verdict)
        risk = RiskClass.unknown
        action = PolicyAction.review_required
    elif interface.breaking_changes:
        overrides.append("breaking-interface-change")
        risk = RiskClass.unknown
        action = PolicyAction.review_required
    elif maintainability.block_merge:
        overrides.append("maintainability-gate")
        risk = RiskClass.unknown
        action = PolicyAction.review_required
    else:
        risk = RiskClass.safe
        action = PolicyAction.merge_supporting
    return PatchRiskResult(
        diff_id=feature_vector.diff_id,
        risk_class=risk,
        calibrated_probability=None,
        ece_bucket=None,
        feature_vector_ref=f"memory://patch/{feature_vector.diff_id}/features",
        active_overrides=overrides,
        calibration_family="unknown",
        confidence="heuristic" if risk is not RiskClass.unknown else "unknown",
        policy_action=action,
    )
