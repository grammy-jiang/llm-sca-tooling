"""Typed evaluation records for Phase 10."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


def utc_now_ts() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def new_eval_run_id() -> str:
    return f"eval:{secrets.token_hex(16)}"


class EvalStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class CanaryVerdict(StrEnum):
    CLEAN = "clean"
    SUSPECT = "suspect"
    CONTAMINATED = "contaminated"
    UNKNOWN = "unknown"


class GateResult(StrictBaseModel):
    gate_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    passed: bool
    evidence_refs: list[str] = Field(default_factory=list)
    diagnostics: list[JsonObject] = Field(default_factory=list)
    computed_ts: str = Field(default_factory=utc_now_ts)


class RDSFeatureVector(StrictBaseModel):
    instance_id: str = Field(min_length=1)
    eval_run_id: str = Field(min_length=1)
    files_touched: int | None = Field(default=None, ge=0)
    chain_depth: int | None = Field(default=None, ge=0)
    cross_file_dataflow: int | None = Field(default=None, ge=0)
    ambient_warning_load: int | None = Field(default=None, ge=0)
    test_brittleness: float | None = Field(default=None, ge=0.0, le=1.0)
    memorisation_distance: float = Field(default=0.5, ge=0.0, le=1.0)
    memorisation_calibrated: bool = False
    computed_ts: str = Field(default_factory=utc_now_ts)
    source_snapshot_id: str | None = None
    provenance: JsonObject = Field(default_factory=dict)
    diagnostics: dict[str, str] = Field(default_factory=dict)


class ContaminationCanaryResult(StrictBaseModel):
    canary_id: str = Field(min_length=1)
    eval_run_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    probe_instance_id: str | None = None
    memorisation_distance_raw: float | None = Field(default=None, ge=0.0, le=1.0)
    canary_verdict: CanaryVerdict = CanaryVerdict.UNKNOWN
    canary_ts: str = Field(default_factory=utc_now_ts)
    diagnostics: list[JsonObject] = Field(default_factory=list)


class FreshnessRecord(StrictBaseModel):
    suite_id: str = Field(min_length=1)
    suite_version: str = Field(min_length=1)
    median_age_days: float | None = Field(default=None, ge=0.0)
    oldest_instance_ts: str | None = None
    newest_instance_ts: str | None = None
    last_refresh_ts: str | None = None
    freshness_check_ts: str = Field(default_factory=utc_now_ts)
    warnings: list[str] = Field(default_factory=list)


class FlakyTestRecord(StrictBaseModel):
    instance_id: str = Field(min_length=1)
    eval_run_id: str = Field(min_length=1)
    flaky_flag: bool
    entropy_score: float = Field(ge=0.0)
    rerun_count: int = Field(ge=0)
    pass_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    detection_method: str = Field(min_length=1)
    excluded_from_aggregate: bool


class FLMetricInstanceResult(StrictBaseModel):
    instance_id: str = Field(min_length=1)
    eval_run_id: str = Field(min_length=1)
    language: str | None = None
    gold_files: list[str]
    ranked_files: list[str]
    budget_n: int = Field(ge=1)
    multi_file: bool
    fl_top1_correct: bool
    fl_top3_correct: bool
    fl_topN_correct: bool  # noqa: N815 - Phase 10 contract spelling.
    repair_correct: bool
    fl_conditioned_repair_correct: bool


class FLMetricsAggregator(StrictBaseModel):
    eval_run_id: str = Field(min_length=1)
    instance_count: int = Field(ge=0)
    single_file_count: int = Field(ge=0)
    multi_file_count: int = Field(ge=0)
    top1_rate: float = Field(ge=0.0, le=1.0)
    top3_rate: float = Field(ge=0.0, le=1.0)
    topN_rate: float = Field(ge=0.0, le=1.0)  # noqa: N815
    repair_rate: float = Field(ge=0.0, le=1.0)
    fl_conditioned_repair_rate: float = Field(ge=0.0, le=1.0)
    per_instance_results: list[FLMetricInstanceResult] = Field(default_factory=list)
    per_language_breakdown: dict[str, JsonObject] = Field(default_factory=dict)


class OperationalQualityMetrics(StrictBaseModel):
    eval_run_id: str = Field(min_length=1)
    process_compliance_rate: float = Field(ge=0.0, le=1.0)
    trace_replay_success_rate: float = Field(ge=0.0, le=1.0)
    policy_violation_count: int = Field(ge=0)
    budget_hard_stop_count: int = Field(ge=0)
    incident_recidivism_rate: float = Field(ge=0.0, le=1.0)
    promotion_precision_placeholder: float = Field(ge=0.0, le=1.0)
    cost_per_accepted_verdict: float | None = Field(default=None, ge=0.0)
    readiness_delta: float = 0.0
    computed_ts: str = Field(default_factory=utc_now_ts)


class MaintainabilityOracleResult(StrictBaseModel):
    oracle_run_id: str = Field(min_length=1)
    diff_id: str = Field(min_length=1)
    change_locality_score: float = Field(ge=0.0, le=1.0)
    dependency_direction_pass: bool
    responsibility_pass: bool
    reuse_pass: bool
    side_effect_pass: bool
    testability_pass: bool
    overall_pass: bool
    findings: list[JsonObject] = Field(default_factory=list)
    diagnostics: list[JsonObject] = Field(default_factory=list)
    computed_ts: str = Field(default_factory=utc_now_ts)


class AIReadinessReport(StrictBaseModel):
    report_id: str = Field(min_length=1)
    repo_id: str = Field(min_length=1)
    eval_run_id: str = Field(min_length=1)
    harness_stage: str = Field(min_length=1)
    agent_config_score: int = Field(ge=0, le=5)
    documentation_score: int = Field(ge=0, le=5)
    ci_cd_score: int = Field(ge=0, le=5)
    code_structure_score: int = Field(ge=0, le=5)
    security_score: int = Field(ge=0, le=5)
    total_score: int = Field(ge=0, le=25)
    stage_threshold_met: bool
    axis_findings: dict[str, list[str]] = Field(default_factory=dict)
    readiness_delta_from_last: int | None = None
    no_regression_check_pass: bool
    computed_ts: str = Field(default_factory=utc_now_ts)


class ManifestRegressionResult(StrictBaseModel):
    run_id: str = Field(min_length=1)
    eval_run_id: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    changed_items: list[str] = Field(default_factory=list)
    findings: list[JsonObject] = Field(default_factory=list)
    overall_verdict: str = Field(min_length=1)
    computed_ts: str = Field(default_factory=utc_now_ts)


class EvalInstanceResult(StrictBaseModel):
    instance_id: str = Field(min_length=1)
    eval_run_id: str = Field(min_length=1)
    suite_id: str = Field(min_length=1)
    issue_ref: str = Field(min_length=1)
    gold_patch_ref: str = Field(min_length=1)
    candidate_patch_ref: str | None = None
    fl_result_ref: str | None = None
    fl_top1_correct: bool
    fl_top3_correct: bool
    fl_topN_correct: bool  # noqa: N815 - Phase 10 contract spelling.
    fl_conditioned_repair_correct: bool
    repair_correct: bool
    gate_results: list[GateResult]
    rds_features: RDSFeatureVector
    contamination_flag: bool
    flaky_flag: bool
    wall_ms: int = Field(ge=0)
    token_count: int = Field(ge=0)
    budget_events: list[JsonObject] = Field(default_factory=list)
    incident_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EvalRun(StrictBaseModel):
    eval_run_id: str = Field(default_factory=new_eval_run_id)
    suite_id: str = Field(min_length=1)
    suite_version: str = Field(min_length=1)
    suite_median_age_days: float | None = Field(default=None, ge=0.0)
    target_workflow: str = Field(min_length=1)
    target_tool: str = Field(min_length=1)
    model_backend: str = Field(min_length=1)
    toolset_hash: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    permission_profile: str = Field(min_length=1)
    harness_condition_id: str = Field(min_length=1)
    start_ts: str = Field(default_factory=utc_now_ts)
    end_ts: str | None = None
    status: EvalStatus
    instance_count: int = Field(ge=0)
    instance_results_ref: str | None = None
    aggregate_metrics_ref: str | None = None
    rds_summary_ref: str | None = None
    operational_metrics_ref: str | None = None
    contamination_canary_result: ContaminationCanaryResult
    freshness_check_ts: str
    artefact_manifest_ref: str | None = None
    run_record_id: str | None = None
    notes: list[str] = Field(default_factory=list)
    instance_results: list[EvalInstanceResult] = Field(default_factory=list)
    aggregate_metrics: FLMetricsAggregator | None = None
    rds_summary: JsonObject | None = None
    operational_metrics: OperationalQualityMetrics | None = None
    freshness_record: FreshnessRecord | None = None
    harness_condition: JsonObject | None = None
    manifest_regression: ManifestRegressionResult | None = None
    ai_readiness_report: AIReadinessReport | None = None
    artifact_manifest: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_instance_count(self) -> EvalRun:
        if self.instance_results and self.instance_count != len(self.instance_results):
            raise ValueError("instance_count must match instance_results length")
        return self
