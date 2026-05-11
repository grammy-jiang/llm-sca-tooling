"""Patch-review models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm_sca_tooling.evaluation.models import now_ts


class StrictPatchModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RiskClass(str, Enum):
    safe = "safe"
    correct_but_overfit = "correct-but-overfit"
    vulnerable = "vulnerable"
    vulnerability_introducing = "vulnerability-introducing"
    unknown = "unknown"


class PolicyAction(str, Enum):
    merge_supporting = "merge-supporting"
    review_required = "review-required"
    block = "block"
    unknown = "unknown"


class DiffHunk(StrictPatchModel):
    file_path: str
    old_start: int
    new_start: int
    added_lines: list[str] = Field(default_factory=list)
    removed_lines: list[str] = Field(default_factory=list)


class DiffRecord(StrictPatchModel):
    diff_id: str
    diff_text: str
    diff_format: str = "unified"
    changed_files: list[str]
    hunks: list[DiffHunk]
    added_lines: int
    removed_lines: int
    net_lines: int
    snapshot_before_id: str | None = None
    snapshot_after_id: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)


class ChangedSymbolRecord(StrictPatchModel):
    diff_id: str
    file_path: str
    symbol_path: str
    symbol_type: str
    change_kind: str
    span_before: tuple[int, int] | None = None
    span_after: tuple[int, int] | None = None
    graph_node_id: str | None = None
    confidence: str = "heuristic"
    is_generated: bool = False
    is_public_api: bool = False
    is_interface_boundary: bool = False


class ASTDiffFeatures(StrictPatchModel):
    diff_id: str
    changed_node_kinds: list[str]
    edit_operation: str
    touched_symbol_count: int
    edit_distance_proxy: int
    generated_or_stub_flag: bool
    signature_changed: bool
    return_type_changed: bool
    parameter_count_delta: int
    raises_new_exception: bool
    security_sensitive_annotation_removed: bool
    confidence: str


class GraphContextRecord(StrictPatchModel):
    diff_id: str
    changed_symbol_ids: list[str]
    two_hop_callers: list[str] = Field(default_factory=list)
    two_hop_callees: list[str] = Field(default_factory=list)
    cross_file_dataflow_edges: list[str] = Field(default_factory=list)
    interface_boundary_nodes: list[str] = Field(default_factory=list)
    tests_exercising_changed_nodes: list[str] = Field(default_factory=list)
    test_count: int | None = None
    coverage_available: bool = False
    snapshot_id: str | None = None
    confidence: str = "heuristic"
    diagnostics: list[str] = Field(default_factory=list)


class SARIFDeltaRecord(StrictPatchModel):
    diff_id: str
    new_alerts: list[dict[str, Any]] = Field(default_factory=list)
    fixed_alerts: list[dict[str, Any]] = Field(default_factory=list)
    severity_changed: list[dict[str, Any]] = Field(default_factory=list)
    location_changed: list[dict[str, Any]] = Field(default_factory=list)
    has_new_critical: bool = False
    has_new_security: bool = False


class TestDeltaRecord(StrictPatchModel):
    diff_id: str
    tests_run: int
    tests_passed_before: int
    tests_passed_after: int
    tests_failed_before: int
    tests_failed_after: int
    newly_failing: list[str] = Field(default_factory=list)
    newly_passing: list[str] = Field(default_factory=list)
    reproduction_test_result: str = "not_available"
    poc_plus_result: str = "not_available"
    flaky_rerun_entropy: float = 0.0
    confidence: str = "heuristic"


class InterfaceCompatibilityResult(StrictPatchModel):
    diff_id: str
    interface_type: str
    changed_operations: list[str] = Field(default_factory=list)
    affected_consumers: list[str] = Field(default_factory=list)
    breaking_changes: list[str] = Field(default_factory=list)
    candidate_changes: list[str] = Field(default_factory=list)
    generated_file_impact: list[str] = Field(default_factory=list)
    confidence: str = "heuristic"
    diagnostics: list[str] = Field(default_factory=list)


class DryRUNPrediction(StrictPatchModel):
    diff_id: str
    intended_behaviour_change: str
    expected_files_changed: list[str]
    expected_test_cases_passing: list[str] = Field(default_factory=list)
    expected_test_cases_failing: list[str] = Field(default_factory=list)
    expected_positive_cases: list[str] = Field(default_factory=list)
    expected_negative_cases: list[str] = Field(default_factory=list)
    expected_edge_cases: list[str] = Field(default_factory=list)
    predicted_outputs: dict[str, Any] = Field(default_factory=dict)
    predicted_side_effects: list[str] = Field(default_factory=list)
    stated_invariants: list[str] = Field(default_factory=list)
    stated_risks: list[str] = Field(default_factory=list)
    generator: str = "phase11-null"
    confidence: str = "heuristic"


class DryRUNMismatch(StrictPatchModel):
    diff_id: str
    prediction_id: str
    mismatch_type: str
    predicted_value: Any
    actual_value: Any
    severity: str
    residual_risk_note: str
    trace_divergence_ref: str | None = None


class ScopeAuditResult(StrictPatchModel):
    run_id: str | None = None
    changed_paths: list[str]
    allowlisted_paths: list[str]
    out_of_scope_writes: list[str]
    tool_calls_vs_mode: dict[str, str] = Field(default_factory=dict)
    network_use_vs_policy: dict[str, str] = Field(default_factory=dict)
    required_events_present: bool
    approval_events_present: bool = False
    denial_events_present: bool = False
    budget_events_present: bool = True
    compaction_events_present: bool = False
    missing_required_events: list[str] = Field(default_factory=list)
    trace_complete: bool
    process_verdict: str


class MaintainabilityGateResult(StrictPatchModel):
    diff_id: str
    oracle_result_id: str
    change_locality_pass: bool
    dependency_direction_pass: bool
    responsibility_pass: bool
    reuse_pass: bool
    side_effect_pass: bool
    testability_pass: bool
    overall_pass: bool
    findings: list[str] = Field(default_factory=list)
    block_merge: bool


class PatchRiskFeatureVector(StrictPatchModel):
    diff_id: str
    ast_diff_features_ref: str
    sarif_delta_ref: str
    graph_context_ref: str
    test_delta_ref: str
    vulnerability_prior_cwe: str | None = None
    vulnerability_prior_rule_family: str | None = None
    vulnerability_prior_probability: float | None = None
    vulnerability_prior_calibrated: bool = False
    interface_compatibility_ref: str
    dryrun_mismatch_count: int
    scope_audit_verdict: str
    maintainability_gate_pass: bool


class PatchRiskResult(StrictPatchModel):
    diff_id: str
    risk_class: RiskClass
    calibrated_probability: float | None = None
    ece_bucket: str | None = None
    feature_vector_ref: str
    active_overrides: list[str] = Field(default_factory=list)
    classifier_version: str = "phase11-deterministic"
    calibration_family: str = "unknown"
    confidence: str = "heuristic"
    policy_action: PolicyAction


class AxisFinding(StrictPatchModel):
    axis: str
    findings: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    risk_signals: list[str] = Field(default_factory=list)
    confidence: str = "heuristic"
    sampling_used: bool = False
    reviewer_id: str


class OperationalIntegrationResult(StrictPatchModel):
    run_id: str | None = None
    process_verdict: str
    incident_count: int = 0
    incident_ids: list[str] = Field(default_factory=list)
    trace_complete: bool
    budget_hard_stop: bool = False
    policy_violation_count: int = 0
    missing_required_events: list[str] = Field(default_factory=list)
    operational_recommendation: PolicyAction


class PatchReviewReport(StrictPatchModel):
    report_id: str
    diff_id: str
    run_id: str | None = None
    harness_condition_id: str
    correctness_finding: AxisFinding
    security_finding: AxisFinding
    performance_finding: AxisFinding
    compatibility_finding: AxisFinding
    sarif_delta_ref: str
    test_delta_ref: str
    interface_compat_result_ref: str
    dryrun_prediction_ref: str
    dryrun_mismatches: list[DryRUNMismatch] = Field(default_factory=list)
    scope_audit_result_ref: str
    maintainability_gate_result_ref: str
    patch_risk_result_ref: str
    recommendation: PolicyAction
    operational_verdict: str
    incident_links: list[str] = Field(default_factory=list)
    uncertainty: str
    sampling_used: bool
    fallback_mode: bool
    created_ts: str = Field(default_factory=now_ts)
