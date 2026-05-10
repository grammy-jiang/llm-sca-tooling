"""Patch-risk feature-vector assembler."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import (
    ASTDiffFeatures,
    GraphContextRecord,
    InterfaceCompatibilityResult,
    MaintainabilityGateResult,
    PatchRiskFeatureVector,
    ProcessVerdict,
    SARIFDelta,
    ScopeAuditResult,
    TestDeltaRecord,
)


def assemble_feature_vector(
    *,
    diff_id: str,
    ast_features: ASTDiffFeatures | None = None,
    sarif_delta: SARIFDelta | None = None,
    graph_context: GraphContextRecord | None = None,
    test_delta: TestDeltaRecord | None = None,
    interface_compat: InterfaceCompatibilityResult | None = None,
    scope_audit: ScopeAuditResult | None = None,
    maintainability: MaintainabilityGateResult | None = None,
    dryrun_mismatch_count: int = 0,
    vulnerability_prior_cwe: str | None = None,
    vulnerability_prior_rule_family: str | None = None,
    vulnerability_prior_probability: float | None = None,
    vulnerability_prior_calibrated: bool = False,
) -> PatchRiskFeatureVector:
    """Assemble a typed feature vector from upstream gate signals."""
    return PatchRiskFeatureVector(
        diff_id=diff_id,
        ast_diff_features_ref=ast_features.diff_id if ast_features else None,
        sarif_delta_ref=sarif_delta.diff_id if sarif_delta else None,
        graph_context_ref=graph_context.diff_id if graph_context else None,
        test_delta_ref=test_delta.diff_id if test_delta else None,
        vulnerability_prior_cwe=vulnerability_prior_cwe,
        vulnerability_prior_rule_family=vulnerability_prior_rule_family,
        vulnerability_prior_probability=vulnerability_prior_probability,
        vulnerability_prior_calibrated=vulnerability_prior_calibrated,
        interface_compatibility_ref=(
            interface_compat.diff_id if interface_compat else None
        ),
        dryrun_mismatch_count=dryrun_mismatch_count,
        scope_audit_verdict=(
            scope_audit.process_verdict if scope_audit else ProcessVerdict.UNKNOWN
        ),
        maintainability_gate_pass=(
            maintainability.overall_pass if maintainability else True
        ),
    )
