"""Patch-risk feature vector assembly."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import (
    ASTDiffFeatures,
    InterfaceCompatibilityResult,
    MaintainabilityGateResult,
    PatchRiskFeatureVector,
    ScopeAuditResult,
)


def assemble_feature_vector(
    *,
    diff_id: str,
    ast_features: ASTDiffFeatures,
    interface: InterfaceCompatibilityResult,
    scope: ScopeAuditResult,
    maintainability: MaintainabilityGateResult,
    dryrun_mismatch_count: int,
) -> PatchRiskFeatureVector:
    return PatchRiskFeatureVector(
        diff_id=diff_id,
        ast_diff_features_ref=f"memory://patch/{diff_id}/ast",
        sarif_delta_ref=f"memory://patch/{diff_id}/sarif",
        graph_context_ref=f"memory://patch/{diff_id}/graph",
        test_delta_ref=f"memory://patch/{diff_id}/tests",
        vulnerability_prior_cwe=None,
        vulnerability_prior_rule_family=None,
        vulnerability_prior_probability=None,
        vulnerability_prior_calibrated=False,
        interface_compatibility_ref=f"memory://patch/{diff_id}/interface",
        dryrun_mismatch_count=dryrun_mismatch_count,
        scope_audit_verdict=scope.process_verdict,
        maintainability_gate_pass=not maintainability.block_merge,
    )
