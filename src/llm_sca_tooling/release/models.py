"""Phase 18 release-gate and calibration models."""

from __future__ import annotations

import secrets
from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from llm_sca_tooling.evaluation.models import now_ts

__all__ = [
    "AblationConfig",
    "AblationControlChange",
    "AblationDelta",
    "AblationReport",
    "AdversarialCheckResult",
    "BenchmarkSuiteResult",
    "CalibrationOracle",
    "CalibrationReport",
    "CalibrationSample",
    "OperationalHarnessGateResult",
    "OperationalReviewReport",
    "ProductionEvalRefreshRecord",
    "ReadinessAuditReport",
    "ReleaseGateResult",
    "ReleaseImpact",
    "StrictReleaseModel",
    "new_release_id",
]


def new_release_id(prefix: str) -> str:
    return f"{prefix}:{secrets.token_urlsafe(18)}"


class StrictReleaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReleaseImpact(str, Enum):
    no_impact = "no_impact"
    unexpected_improvement = "unexpected_improvement"
    unexpected_degradation = "unexpected_degradation"
    expected_degradation = "expected_degradation"


class CalibrationSample(StrictReleaseModel):
    sample_id: str
    family: str = "unknown"
    predicted_probability: float = Field(ge=0.0, le=1.0)
    predicted_label: str
    gold_label: str

    @property
    def correct(self) -> bool:
        return self.predicted_label == self.gold_label


class CalibrationOracle(StrictReleaseModel):
    """Pairs a ``CalibrationSample`` with the clause text pattern it satisfies.

    Phase 18 §5 calibration fixtures play two roles:

    1. *Metric role* — ``sample`` contributes to ECE / macro-F1 over the
       impl-check sample population.
    2. *Auto-pass oracle role* — when ``calibration_available=True`` the
       impl-check aggregator checks every behavioural clause's text
       against every oracle's ``clause_text_pattern``; a substring match
       moves the clause from ``unknown`` to ``satisfied`` with
       ``dominant_evidence: "calibrated_oracle"``.

    Substring matching (not regex) is deliberate: the matching condition
    is introspectable from the fixture file alone, and widening to regex
    later is a forward-compatible change.
    """

    sample: CalibrationSample
    clause_text_pattern: str = Field(min_length=3)


class CalibrationReport(StrictReleaseModel):
    report_id: str = Field(default_factory=lambda: new_release_id("calibration"))
    eval_run_id: str
    model_backend: str
    harness_condition_id: str
    patch_risk_ece: float = Field(ge=0.0, le=1.0)
    patch_risk_macro_f1: float = Field(ge=0.0, le=1.0)
    patch_risk_calibration_family: str
    patch_risk_gate_passed: bool
    impl_check_ece_per_clause_family: dict[str, float]
    impl_check_gate_passed: bool
    repo_qa_file_loc_accuracy: float = Field(ge=0.0, le=1.0)
    repo_qa_behaviour_tracing_accuracy: float = Field(ge=0.0, le=1.0)
    repo_qa_behaviour_gate_passed: bool
    memory_her_eviction_delta_pp: float
    memory_ship_gate_passed: bool
    rds_v2_summary: dict[str, Any] = Field(default_factory=dict)
    computed_ts: str = Field(default_factory=now_ts)


class AblationControlChange(StrictReleaseModel):
    control_name: str
    before_value: str
    after_value: str


class AblationConfig(StrictReleaseModel):
    ablation_id: str
    baseline_config_ref: str
    modified_controls: list[AblationControlChange]
    rationale: str

    @model_validator(mode="after")
    def _exactly_one_control_changes(self) -> Self:
        if len(self.modified_controls) != 1:
            raise ValueError("exactly one control must change per ablation")
        change = self.modified_controls[0]
        if change.before_value == change.after_value:
            raise ValueError(
                "ablation control before_value and after_value must differ"
            )
        return self


class AblationDelta(StrictReleaseModel):
    ablation_id: str
    resolve_rate_delta: float
    policy_compliance_delta: float
    trace_replay_delta: float
    release_impact: ReleaseImpact
    investigation_note: str | None = None


class AblationReport(StrictReleaseModel):
    report_id: str = Field(default_factory=lambda: new_release_id("ablation"))
    baseline_eval_run_id: str
    ablation_configs: list[AblationConfig]
    ablation_eval_run_ids: list[str]
    per_ablation_delta: list[AblationDelta]
    summary_findings: list[str] = Field(default_factory=list)
    release_impact: ReleaseImpact
    created_ts: str = Field(default_factory=now_ts)


class OperationalHarnessGateResult(StrictReleaseModel):
    gate_id: str = Field(default_factory=lambda: new_release_id("operational-gate"))
    eval_run_id: str
    trace_completeness_rate: float = Field(ge=0.0, le=1.0)
    policy_compliance_rate: float = Field(ge=0.0, le=1.0)
    budget_reliability_rate: float = Field(ge=0.0, le=1.0)
    maintainability_oracle_pass_rate: float = Field(ge=0.0, le=1.0)
    manifest_regression_pass_rate: float = Field(ge=0.0, le=1.0)
    readiness_threshold_met: bool
    p0_p1_incident_closure_rate: float = Field(ge=0.0, le=1.0)
    trace_replay_success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    policy_violation_count: int = Field(default=0, ge=0)
    budget_hard_stop_count: int = Field(default=0, ge=0)
    incident_recidivism_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    cost_per_accepted_verdict: float = Field(default=0.0, ge=0.0)
    gate_passed: bool
    failing_gates: list[str] = Field(default_factory=list)
    computed_ts: str = Field(default_factory=now_ts)


class AdversarialCheckResult(StrictReleaseModel):
    check_id: str
    check_type: str
    fixture_id: str
    input_ref: str
    expected_outcome: str
    actual_outcome: str
    passed: bool
    evidence_refs: list[str] = Field(default_factory=list)
    created_ts: str = Field(default_factory=now_ts)


class ProductionEvalRefreshRecord(StrictReleaseModel):
    refresh_id: str = Field(default_factory=lambda: new_release_id("refresh"))
    source_run_id: str
    issue_text_hash: str
    repo_id: str
    gold_patch_hidden: bool
    fail_to_pass_tests_present: bool
    pass_to_pass_tests_present: bool
    test_relevance_validated: bool
    flaky_flag: bool
    approved: bool
    added_to_suite_id: str | None = None
    created_ts: str = Field(default_factory=now_ts)


class BenchmarkSuiteResult(StrictReleaseModel):
    suite_id: str
    eval_run_id: str
    status: str
    passed: bool
    metrics: dict[str, float] = Field(default_factory=dict)
    freshness_days: float = 0.0


class ReleaseGateResult(StrictReleaseModel):
    gate_run_id: str = Field(default_factory=lambda: new_release_id("release-gate"))
    harness_condition_id: str
    benchmark_results: list[BenchmarkSuiteResult]
    calibration_report_ref: str | None = None
    ablation_report_ref: str | None = None
    operational_gate_result_ref: str | None = None
    adversarial_check_results: list[AdversarialCheckResult] = Field(
        default_factory=list
    )
    memory_ship_gate_result_ref: str | None = None
    ai_readiness_report_ref: str | None = None
    disabled_gates: list[str] = Field(default_factory=list)
    overall_pass: bool
    failing_gates: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    created_ts: str = Field(default_factory=now_ts)


class OperationalReviewReport(StrictReleaseModel):
    report_id: str = Field(default_factory=lambda: new_release_id("op-review"))
    run_id: str
    process_compliance_verdict: str
    trace_completeness: str
    denied_actions: list[str] = Field(default_factory=list)
    approved_actions: list[str] = Field(default_factory=list)
    budget_behaviour: str
    compaction_loss: str
    verification_adequacy: str
    maintainability_oracle_results: list[str] = Field(default_factory=list)
    lessons_eligible_for_promotion: list[str] = Field(default_factory=list)
    harness_condition_id: str | None = None
    created_ts: str = Field(default_factory=now_ts)


class ReadinessAuditReport(StrictReleaseModel):
    report_id: str = Field(default_factory=lambda: new_release_id("readiness-audit"))
    repo: str
    ai_readiness_score: int
    harness_stage: str
    drift_findings: list[str] = Field(default_factory=list)
    missing_gates: list[str] = Field(default_factory=list)
    weak_docs_spec_links: list[str] = Field(default_factory=list)
    unprotected_risky_paths: list[str] = Field(default_factory=list)
    absent_scanners: list[str] = Field(default_factory=list)
    recommended_readiness_tasks: list[str] = Field(default_factory=list)
    ai_readiness_report_ref: str
    created_ts: str = Field(default_factory=now_ts)
