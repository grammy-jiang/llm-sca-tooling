"""Deterministic patch-risk policy used until the trained classifier is calibrated."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import (
    ConfidenceLevel,
    InterfaceCompatibilityResult,
    MaintainabilityGateResult,
    PatchRiskFeatureVector,
    PatchRiskResult,
    PolicyActionValue,
    ProcessVerdict,
    RiskClassValue,
    SARIFDelta,
    ScopeAuditResult,
    TestDeltaRecord,
)
from llm_sca_tooling.patch_review.test_delta import (
    has_failing_required_test,
    reproduction_test_is_invalid,
)


def apply_deterministic_policy(
    feature_vector: PatchRiskFeatureVector,
    *,
    sarif_delta: SARIFDelta | None,
    test_delta: TestDeltaRecord | None,
    interface_compat: InterfaceCompatibilityResult | None,
    scope_audit: ScopeAuditResult | None,
    maintainability: MaintainabilityGateResult | None,
    required_tests: list[str] | None = None,
    poc_required: bool = False,
    calibration_family: str | None = None,
) -> PatchRiskResult:
    """Apply the Phase 11 deterministic risk policy.

    Returns a typed :class:`PatchRiskResult` with the active overrides
    populated. The function is the only place where the rule-table is
    encoded; downstream callers must not duplicate any of the rules.
    """
    overrides: list[str] = []

    new_critical_or_security = False
    if sarif_delta and sarif_delta.available:
        if sarif_delta.new_critical_count > 0:
            overrides.append("sarif_new_critical")
            new_critical_or_security = True
        if sarif_delta.new_security_count > 0:
            overrides.append("sarif_new_security")
            new_critical_or_security = True

    failing_required = False
    if test_delta is not None and has_failing_required_test(test_delta, required_tests):
        overrides.append("failing_required_test")
        failing_required = True

    invalid_repro = test_delta is not None and reproduction_test_is_invalid(test_delta)
    if invalid_repro:
        overrides.append("invalid_reproduction_test")

    poc_failed = False
    if poc_required and test_delta is not None:
        if test_delta.poc_plus_result.value == "failed":
            overrides.append("poc_plus_failed")
            poc_failed = True

    out_of_scope = bool(scope_audit and scope_audit.out_of_scope_writes)
    if out_of_scope:
        overrides.append("out_of_scope_write")

    process_verdict = (
        scope_audit.process_verdict if scope_audit else ProcessVerdict.UNKNOWN
    )
    process_problem = process_verdict in {
        ProcessVerdict.TRACE_INCOMPLETE,
        ProcessVerdict.BUDGET_EXHAUSTED,
        ProcessVerdict.PROCESS_NONCOMPLIANT,
        ProcessVerdict.UNKNOWN,
    }

    breaking_iface = bool(interface_compat and interface_compat.breaking_changes)
    if breaking_iface:
        overrides.append("interface_breaking_change")

    dep_direction_failed = bool(
        maintainability and not maintainability.dependency_direction_pass
    )
    if dep_direction_failed:
        overrides.append("dependency_direction_failed")
    if maintainability and maintainability.block_merge:
        overrides.append("maintainability_block")

    calibration_missing = calibration_family is None

    risk_class: RiskClassValue
    policy_action: PolicyActionValue
    confidence = ConfidenceLevel.ANALYSER
    calibrated_probability: float | None = None

    if new_critical_or_security:
        risk_class = RiskClassValue.VULNERABILITY_INTRODUCING
        policy_action = PolicyActionValue.BLOCK
        calibrated_probability = 0.95
    elif failing_required and invalid_repro:
        risk_class = RiskClassValue.CORRECT_BUT_OVERFIT
        policy_action = PolicyActionValue.BLOCK
        calibrated_probability = 0.85
    elif poc_failed:
        risk_class = RiskClassValue.VULNERABLE
        policy_action = PolicyActionValue.BLOCK
        calibrated_probability = 0.9
    elif failing_required:
        risk_class = RiskClassValue.CORRECT_BUT_OVERFIT
        policy_action = PolicyActionValue.BLOCK
        calibrated_probability = 0.8
    elif out_of_scope:
        risk_class = RiskClassValue.UNKNOWN
        policy_action = PolicyActionValue.BLOCK
        confidence = ConfidenceLevel.HEURISTIC
    elif process_problem:
        risk_class = RiskClassValue.UNKNOWN
        policy_action = PolicyActionValue.UNKNOWN
        confidence = ConfidenceLevel.UNKNOWN
    elif breaking_iface:
        risk_class = RiskClassValue.UNKNOWN
        policy_action = PolicyActionValue.REVIEW_REQUIRED
        confidence = ConfidenceLevel.HEURISTIC
    elif dep_direction_failed:
        risk_class = RiskClassValue.UNKNOWN
        policy_action = PolicyActionValue.REVIEW_REQUIRED
        confidence = ConfidenceLevel.HEURISTIC
    elif maintainability and maintainability.block_merge:
        risk_class = RiskClassValue.UNKNOWN
        policy_action = PolicyActionValue.REVIEW_REQUIRED
        confidence = ConfidenceLevel.HEURISTIC
    elif calibration_missing:
        risk_class = RiskClassValue.SAFE
        policy_action = PolicyActionValue.MERGE_SUPPORTING
        calibrated_probability = 0.6
        confidence = ConfidenceLevel.HEURISTIC
    else:
        risk_class = RiskClassValue.SAFE
        policy_action = PolicyActionValue.MERGE_SUPPORTING
        calibrated_probability = 0.7

    return PatchRiskResult(
        diff_id=feature_vector.diff_id,
        risk_class=risk_class,
        calibrated_probability=calibrated_probability,
        ece_bucket=None,
        feature_vector_ref=feature_vector.diff_id,
        active_overrides=overrides,
        classifier_version="deterministic-v1",
        calibration_family=calibration_family,
        confidence=confidence,
        policy_action=policy_action,
    )
