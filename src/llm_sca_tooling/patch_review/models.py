"""Pydantic v2 models for Phase 11 patch-review and risk gates."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, id_field


class ConfidenceLevel(StrEnum):
    ANALYSER = "analyser"
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"


class ChangeKind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED_SIGNATURE = "modified_signature"
    MODIFIED_BODY = "modified_body"
    MODIFIED_DOCSTRING = "modified_docstring"
    RENAMED = "renamed"
    UNKNOWN = "unknown"


class EditOperation(StrEnum):
    ADDED_FUNCTION = "added_function"
    REMOVED_FUNCTION = "removed_function"
    SIGNATURE_CHANGE = "signature_change"
    BODY_CHANGE = "body_change"
    CONDITIONAL_INSERTED = "conditional_inserted"
    CONDITIONAL_REMOVED = "conditional_removed"
    LOOP_INSERTED = "loop_inserted"
    LOOP_REMOVED = "loop_removed"
    EXCEPTION_HANDLER_CHANGED = "exception_handler_changed"
    OTHER = "other"


class ReproductionTestResult(StrEnum):
    NOT_AVAILABLE = "not_available"
    GENERATED = "generated"
    EXECUTED_FAIL_BEFORE_PASS_AFTER = "executed_fail_before_pass_after"
    EXECUTED_FAIL_BOTH = "executed_fail_both"
    EXECUTED_PASS_BOTH = "executed_pass_both"
    FLAKY = "flaky"


class PocPlusResult(StrEnum):
    NOT_AVAILABLE = "not_available"
    PASSED = "passed"
    FAILED = "failed"
    FLAKY = "flaky"


class ProcessVerdict(StrEnum):
    PROCESS_COMPLIANT = "process-compliant"
    PROCESS_NONCOMPLIANT = "process-noncompliant"
    TRACE_INCOMPLETE = "trace-incomplete"
    BUDGET_EXHAUSTED = "budget-exhausted"
    UNKNOWN = "unknown"


class RiskClassValue(StrEnum):
    SAFE = "safe"
    CORRECT_BUT_OVERFIT = "correct-but-overfit"
    VULNERABLE = "vulnerable"
    VULNERABILITY_INTRODUCING = "vulnerability-introducing"
    UNKNOWN = "unknown"


class PolicyActionValue(StrEnum):
    MERGE_SUPPORTING = "merge-supporting"
    REVIEW_REQUIRED = "review-required"
    BLOCK = "block"
    UNKNOWN = "unknown"


class Recommendation(StrEnum):
    MERGE_SUPPORTING = "merge-supporting"
    REVIEW_REQUIRED = "review-required"
    BLOCK = "block"
    UNKNOWN = "unknown"


class InterfaceChangeImpact(StrEnum):
    COMPATIBLE = "compatible"
    CANDIDATE = "candidate"
    BREAKING = "breaking"
    CONFIRMED_BREAKING = "confirmed_breaking"


class MismatchType(StrEnum):
    EXTRA_FILES_CHANGED = "extra_files_changed"
    FEWER_FILES_CHANGED = "fewer_files_changed"
    UNEXPECTED_TEST_FAILURE = "unexpected_test_failure"
    UNEXPECTED_TEST_PASS = "unexpected_test_pass"
    UNEXPECTED_SIDE_EFFECT = "unexpected_side_effect"
    INVARIANT_VIOLATED = "invariant_violated"
    STATED_RISK_MATERIALISED = "stated_risk_materialised"


class AuditAxis(StrEnum):
    CORRECTNESS = "correctness"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COMPATIBILITY = "compatibility"


class HunkRecord(StrictBaseModel):
    file_path: str = Field(min_length=1)
    old_start: int = Field(ge=0)
    old_count: int = Field(ge=0)
    new_start: int = Field(ge=0)
    new_count: int = Field(ge=0)
    added_lines: list[str] = Field(default_factory=list)
    removed_lines: list[str] = Field(default_factory=list)
    context_lines: list[str] = Field(default_factory=list)
    header: str | None = None


class DiffRecord(StrictBaseModel):
    diff_id: str = id_field("Diff identifier.")
    diff_text: str
    diff_format: str = "unified"
    changed_files: list[str] = Field(default_factory=list)
    hunks: list[HunkRecord] = Field(default_factory=list)
    added_lines: int = Field(ge=0)
    removed_lines: int = Field(ge=0)
    net_lines: int
    snapshot_before_id: str | None = None
    snapshot_after_id: str | None = None
    provenance: JsonObject = Field(default_factory=dict)
    diagnostics: list[JsonObject] = Field(default_factory=list)


class ChangedSymbolRecord(StrictBaseModel):
    diff_id: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    symbol_path: str = Field(min_length=1)
    symbol_type: str = Field(min_length=1)
    change_kind: ChangeKind
    span_before: JsonObject | None = None
    span_after: JsonObject | None = None
    graph_node_id: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC
    is_generated: bool = False
    is_public_api: bool = False
    is_interface_boundary: bool = False


class ASTDiffFeatures(StrictBaseModel):
    diff_id: str = Field(min_length=1)
    changed_node_kinds: list[str] = Field(default_factory=list)
    edit_operation: EditOperation
    touched_symbol_count: int = Field(ge=0)
    edit_distance_proxy: int = Field(ge=0)
    generated_or_stub_flag: bool = False
    signature_changed: bool = False
    return_type_changed: bool = False
    parameter_count_delta: int = 0
    raises_new_exception: bool = False
    security_sensitive_annotation_removed: bool = False
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC


class GraphContextRecord(StrictBaseModel):
    diff_id: str = Field(min_length=1)
    changed_symbol_ids: list[str] = Field(default_factory=list)
    two_hop_callers: list[str] = Field(default_factory=list)
    two_hop_callees: list[str] = Field(default_factory=list)
    cross_file_dataflow_edges: list[JsonObject] = Field(default_factory=list)
    interface_boundary_nodes: list[str] = Field(default_factory=list)
    tests_exercising_changed_nodes: list[str] = Field(default_factory=list)
    test_count: int = Field(ge=0)
    coverage_available: bool = False
    snapshot_id: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC
    diagnostics: list[JsonObject] = Field(default_factory=list)


class SARIFDeltaAlert(StrictBaseModel):
    alert_id: str = Field(min_length=1)
    rule_id: str | None = None
    severity: str | None = None
    cwe: str | None = None
    rule_family: str | None = None
    file_path: str | None = None


class SARIFDelta(StrictBaseModel):
    diff_id: str = Field(min_length=1)
    before_run_id: str | None = None
    after_run_id: str | None = None
    appeared: list[SARIFDeltaAlert] = Field(default_factory=list)
    disappeared: list[SARIFDeltaAlert] = Field(default_factory=list)
    severity_changed: list[SARIFDeltaAlert] = Field(default_factory=list)
    location_changed: list[SARIFDeltaAlert] = Field(default_factory=list)
    new_critical_count: int = Field(ge=0, default=0)
    new_security_count: int = Field(ge=0, default=0)
    available: bool = True
    diagnostics: list[JsonObject] = Field(default_factory=list)


class TestDeltaRecord(StrictBaseModel):
    diff_id: str = Field(min_length=1)
    tests_run: int = Field(ge=0, default=0)
    tests_passed_before: int = Field(ge=0, default=0)
    tests_passed_after: int = Field(ge=0, default=0)
    tests_failed_before: int = Field(ge=0, default=0)
    tests_failed_after: int = Field(ge=0, default=0)
    newly_failing: list[str] = Field(default_factory=list)
    newly_passing: list[str] = Field(default_factory=list)
    reproduction_test_result: ReproductionTestResult = (
        ReproductionTestResult.NOT_AVAILABLE
    )
    poc_plus_result: PocPlusResult = PocPlusResult.NOT_AVAILABLE
    flaky_rerun_entropy: float | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC


class InterfaceCompatibilityResult(StrictBaseModel):
    diff_id: str = Field(min_length=1)
    interface_type: str = "unknown"
    changed_operations: list[str] = Field(default_factory=list)
    affected_consumers: list[str] = Field(default_factory=list)
    breaking_changes: list[JsonObject] = Field(default_factory=list)
    candidate_changes: list[JsonObject] = Field(default_factory=list)
    generated_file_impact: list[JsonObject] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC
    diagnostics: list[JsonObject] = Field(default_factory=list)


class DryRUNPrediction(StrictBaseModel):
    prediction_id: str = id_field("DryRUN prediction identifier.")
    diff_id: str = Field(min_length=1)
    intended_behaviour_change: str = ""
    expected_files_changed: list[str] = Field(default_factory=list)
    expected_test_cases_passing: list[str] = Field(default_factory=list)
    expected_test_cases_failing: list[str] = Field(default_factory=list)
    expected_positive_cases: list[str] = Field(default_factory=list)
    expected_negative_cases: list[str] = Field(default_factory=list)
    expected_edge_cases: list[str] = Field(default_factory=list)
    predicted_outputs: list[JsonObject] = Field(default_factory=list)
    predicted_side_effects: list[str] = Field(default_factory=list)
    stated_invariants: list[str] = Field(default_factory=list)
    stated_risks: list[str] = Field(default_factory=list)
    generator: str = "null-adapter"
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC


class DryRUNMismatch(StrictBaseModel):
    diff_id: str = Field(min_length=1)
    prediction_id: str = Field(min_length=1)
    mismatch_type: MismatchType
    predicted_value: JsonObject = Field(default_factory=dict)
    actual_value: JsonObject = Field(default_factory=dict)
    severity: str = "info"
    residual_risk_note: str = ""
    trace_divergence_ref: str | None = None


class ScopeAuditResult(StrictBaseModel):
    run_id: str | None = None
    changed_paths: list[str] = Field(default_factory=list)
    allowlisted_paths: list[str] = Field(default_factory=list)
    out_of_scope_writes: list[str] = Field(default_factory=list)
    tool_calls_vs_mode: list[JsonObject] = Field(default_factory=list)
    network_use_vs_policy: list[JsonObject] = Field(default_factory=list)
    required_events_present: list[str] = Field(default_factory=list)
    approval_events_present: list[str] = Field(default_factory=list)
    denial_events_present: list[str] = Field(default_factory=list)
    budget_events_present: list[str] = Field(default_factory=list)
    compaction_events_present: list[str] = Field(default_factory=list)
    missing_required_events: list[str] = Field(default_factory=list)
    trace_complete: bool = True
    process_verdict: ProcessVerdict = ProcessVerdict.UNKNOWN


class MaintainabilityGateResult(StrictBaseModel):
    diff_id: str = Field(min_length=1)
    oracle_result_id: str | None = None
    change_locality_pass: bool = True
    dependency_direction_pass: bool = True
    responsibility_pass: bool = True
    reuse_pass: bool = True
    side_effect_pass: bool = True
    testability_pass: bool = True
    overall_pass: bool = True
    findings: list[JsonObject] = Field(default_factory=list)
    block_merge: bool = False


class PatchRiskFeatureVector(StrictBaseModel):
    diff_id: str = Field(min_length=1)
    ast_diff_features_ref: str | None = None
    sarif_delta_ref: str | None = None
    graph_context_ref: str | None = None
    test_delta_ref: str | None = None
    vulnerability_prior_cwe: str | None = None
    vulnerability_prior_rule_family: str | None = None
    vulnerability_prior_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    vulnerability_prior_calibrated: bool = False
    interface_compatibility_ref: str | None = None
    dryrun_mismatch_count: int = Field(ge=0, default=0)
    scope_audit_verdict: ProcessVerdict = ProcessVerdict.UNKNOWN
    maintainability_gate_pass: bool = True


class PatchRiskResult(StrictBaseModel):
    diff_id: str = Field(min_length=1)
    risk_class: RiskClassValue
    calibrated_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    ece_bucket: str | None = None
    feature_vector_ref: str | None = None
    active_overrides: list[str] = Field(default_factory=list)
    classifier_version: str = "deterministic-v1"
    calibration_family: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC
    policy_action: PolicyActionValue


class AxisFinding(StrictBaseModel):
    axis: AuditAxis
    findings: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    risk_signals: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC
    sampling_used: bool = False
    reviewer_id: str = "fallback-local"


class OperationalIntegrationResult(StrictBaseModel):
    run_id: str | None = None
    process_verdict: ProcessVerdict = ProcessVerdict.UNKNOWN
    incident_count: int = Field(ge=0, default=0)
    incident_ids: list[str] = Field(default_factory=list)
    trace_complete: bool = True
    budget_hard_stop: bool = False
    policy_violation_count: int = Field(ge=0, default=0)
    missing_required_events: list[str] = Field(default_factory=list)
    operational_recommendation: Recommendation = Recommendation.UNKNOWN


class PatchReviewReport(StrictBaseModel):
    report_id: str = id_field("Patch-review report identifier.")
    diff_id: str = Field(min_length=1)
    run_id: str | None = None
    harness_condition_id: str | None = None
    correctness_finding: AxisFinding
    security_finding: AxisFinding
    performance_finding: AxisFinding
    compatibility_finding: AxisFinding
    sarif_delta_ref: str | None = None
    test_delta_ref: str | None = None
    interface_compat_result_ref: str | None = None
    dryrun_prediction_ref: str | None = None
    dryrun_mismatches: list[DryRUNMismatch] = Field(default_factory=list)
    scope_audit_result_ref: str | None = None
    maintainability_gate_result_ref: str | None = None
    patch_risk_result_ref: str | None = None
    recommendation: Recommendation
    operational_verdict: ProcessVerdict = ProcessVerdict.UNKNOWN
    incident_links: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    sampling_used: bool = False
    fallback_mode: bool = True
    created_ts: str = Field(min_length=1)
