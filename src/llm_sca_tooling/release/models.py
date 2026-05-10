"""Pydantic models for Phase 18 release gates."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from llm_sca_tooling.evaluation.models import utc_now_ts
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


class ReleaseImpact(StrEnum):
    NO_IMPACT = "no_impact"
    UNEXPECTED_IMPROVEMENT = "unexpected_improvement"
    UNEXPECTED_DEGRADATION = "unexpected_degradation"
    EXPECTED_DEGRADATION = "expected_degradation"


class AdversarialCheckType(StrEnum):
    PROMPT_INJECTION = "prompt_injection"
    DOCUMENT_INJECTION = "document_injection"
    TOOL_BOUNDARY_MISUSE = "tool_boundary_misuse"
    OUT_OF_SCOPE_WRITE = "out_of_scope_write"
    MULTISTEP_POLICY_BYPASS = "multistep_policy_bypass"
    REWARD_HACKABLE_TASK = "reward_hackable_task"


class CalibrationReport(StrictBaseModel):
    report_id: str = Field(min_length=1)
    eval_run_id: str = Field(min_length=1)
    model_backend: str = Field(min_length=1)
    harness_condition_id: str = Field(min_length=1)
    patch_risk_ece: float = Field(ge=0.0, le=1.0)
    patch_risk_macro_f1: float = Field(ge=0.0, le=1.0)
    patch_risk_calibration_family: str = Field(min_length=1)
    patch_risk_gate_passed: bool
    impl_check_ece_per_clause_family: dict[str, float] = Field(default_factory=dict)
    impl_check_gate_passed: bool
    repo_qa_file_loc_accuracy: float = Field(ge=0.0, le=1.0)
    repo_qa_behaviour_tracing_accuracy: float = Field(ge=0.0, le=1.0)
    repo_qa_behaviour_gate_passed: bool
    memory_her_eviction_delta_pp: float
    memory_ship_gate_passed: bool
    rds_v2_summary: JsonObject = Field(default_factory=dict)
    computed_ts: str = Field(default_factory=utc_now_ts)


class AblationControlChange(StrictBaseModel):
    control_name: str = Field(min_length=1)
    before_value: str = Field(min_length=1)
    after_value: str = Field(min_length=1)


class AblationConfig(StrictBaseModel):
    ablation_id: str = Field(min_length=1)
    baseline_config_ref: str = Field(min_length=1)
    modified_controls: list[AblationControlChange]
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_single_change(self) -> AblationConfig:
        if len(self.modified_controls) != 1:
            raise ValueError("exactly one control may change per ablation")
        return self


class AblationReport(StrictBaseModel):
    report_id: str = Field(min_length=1)
    baseline_eval_run_id: str = Field(min_length=1)
    ablation_configs: list[AblationConfig]
    ablation_eval_run_ids: list[str]
    per_ablation_delta: dict[str, JsonObject] = Field(default_factory=dict)
    summary_findings: list[str] = Field(default_factory=list)
    release_impact: ReleaseImpact = ReleaseImpact.NO_IMPACT
    created_ts: str = Field(default_factory=utc_now_ts)


class OperationalHarnessGateResult(StrictBaseModel):
    gate_id: str = Field(min_length=1)
    eval_run_id: str = Field(min_length=1)
    trace_completeness_rate: float = Field(ge=0.0, le=1.0)
    policy_compliance_rate: float = Field(ge=0.0, le=1.0)
    budget_reliability_rate: float = Field(ge=0.0, le=1.0)
    maintainability_oracle_pass_rate: float = Field(ge=0.0, le=1.0)
    manifest_regression_pass_rate: float = Field(ge=0.0, le=1.0)
    readiness_threshold_met: bool
    p0_p1_incident_closure_rate: float = Field(ge=0.0, le=1.0)
    gate_passed: bool
    failing_gates: list[str] = Field(default_factory=list)
    process_compliance_rate: float = Field(ge=0.0, le=1.0)
    trace_replay_success_rate: float = Field(ge=0.0, le=1.0)
    policy_violation_count: int = Field(ge=0)
    budget_hard_stop_count: int = Field(ge=0)
    incident_recidivism_rate: float = Field(ge=0.0, le=1.0)
    cost_per_accepted_verdict: float | None = Field(default=None, ge=0.0)
    computed_ts: str = Field(default_factory=utc_now_ts)


class AdversarialCheckResult(StrictBaseModel):
    check_id: str = Field(min_length=1)
    check_type: AdversarialCheckType
    fixture_id: str = Field(min_length=1)
    input_ref: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)
    actual_outcome: str = Field(min_length=1)
    passed: bool
    evidence_refs: list[str] = Field(default_factory=list)
    created_ts: str = Field(default_factory=utc_now_ts)


class ProductionEvalRefreshRecord(StrictBaseModel):
    refresh_id: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    issue_text_hash: str = Field(min_length=1)
    repo_id: str = Field(min_length=1)
    gold_patch_hidden: bool = True
    fail_to_pass_tests_present: bool
    pass_to_pass_tests_present: bool
    test_relevance_validated: bool
    flaky_flag: bool = False
    approved: bool = False
    added_to_suite_id: str | None = None
    created_ts: str = Field(default_factory=utc_now_ts)


class ReleaseGateResult(StrictBaseModel):
    gate_run_id: str = Field(min_length=1)
    harness_condition_id: str = Field(min_length=1)
    benchmark_results: dict[str, JsonObject] = Field(default_factory=dict)
    calibration_report_ref: str | None = None
    ablation_report_ref: str | None = None
    operational_gate_result_ref: str | None = None
    adversarial_check_results: list[AdversarialCheckResult] = Field(
        default_factory=list
    )
    memory_ship_gate_result_ref: str | None = None
    ai_readiness_report_ref: str | None = None
    overall_pass: bool
    failing_gates: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    created_ts: str = Field(default_factory=utc_now_ts)


class OperationalReviewReport(StrictBaseModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    process_compliance_verdict: str = Field(min_length=1)
    trace_completeness: float = Field(ge=0.0, le=1.0)
    denied_actions: list[str] = Field(default_factory=list)
    approved_actions: list[str] = Field(default_factory=list)
    budget_behaviour: JsonObject = Field(default_factory=dict)
    compaction_loss: JsonObject = Field(default_factory=dict)
    verification_adequacy: str = Field(min_length=1)
    maintainability_oracle_results: JsonObject = Field(default_factory=dict)
    lessons_eligible_for_promotion: list[JsonObject] = Field(default_factory=list)
    created_ts: str = Field(default_factory=utc_now_ts)


class ReadinessAuditReport(StrictBaseModel):
    report_id: str = Field(min_length=1)
    repo_id: str = Field(min_length=1)
    ai_readiness_score: int = Field(ge=0, le=25)
    harness_stage: str = Field(min_length=1)
    drift_findings: list[str] = Field(default_factory=list)
    missing_gates: list[str] = Field(default_factory=list)
    weak_docs_spec_links: list[str] = Field(default_factory=list)
    unprotected_risky_paths: list[str] = Field(default_factory=list)
    absent_scanners: list[str] = Field(default_factory=list)
    recommended_readiness_tasks: list[str] = Field(default_factory=list)
    created_ts: str = Field(default_factory=utc_now_ts)
