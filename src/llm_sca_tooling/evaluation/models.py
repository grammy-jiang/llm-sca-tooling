"""Evaluation harness models."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "AIReadinessReport",
    "ContaminationCanaryResult",
    "EvalInstanceResult",
    "EvalRun",
    "EvalStatus",
    "FlakyTestRecord",
    "FreshnessRecord",
    "MaintainabilityOracleResult",
    "ManifestRegressionResult",
    "OperationalQualityMetrics",
    "RDSFeatureVector",
    "new_eval_run_id",
    "now_ts",
]


class StrictEvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvalStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    partial = "partial"


def now_ts() -> str:
    return datetime.now(UTC).isoformat()


def new_eval_run_id() -> str:
    return f"eval:{secrets.token_urlsafe(18)}"


class ContaminationCanaryResult(StrictEvalModel):
    canary_id: str
    eval_run_id: str
    model_id: str
    probe_instance_id: str
    memorisation_distance_raw: float | None = None
    canary_verdict: str = "unknown"
    canary_ts: str = Field(default_factory=now_ts)


class FreshnessRecord(StrictEvalModel):
    suite_id: str
    suite_version: str
    median_age_days: float
    oldest_instance_ts: str | None = None
    newest_instance_ts: str | None = None
    last_refresh_ts: str | None = None
    freshness_check_ts: str = Field(default_factory=now_ts)


class RDSFeatureVector(StrictEvalModel):
    instance_id: str
    eval_run_id: str
    files_touched: int | None = None
    chain_depth: int | None = None
    cross_file_dataflow: int | None = None
    ambient_warning_load: int | None = None
    test_brittleness: float | None = None
    memorisation_distance: float = 0.5
    memorisation_calibrated: bool = False
    diagnostics: dict[str, str] = Field(default_factory=dict)
    computed_ts: str = Field(default_factory=now_ts)
    source_snapshot_id: str | None = None


class EvalInstanceResult(StrictEvalModel):
    instance_id: str
    eval_run_id: str
    suite_id: str
    issue_ref: str
    gold_patch_ref: str | None = None
    candidate_patch_ref: str | None = None
    fl_result_ref: str | None = None
    fl_top1_correct: bool = False
    fl_top3_correct: bool = False
    fl_topN_correct: bool = False  # noqa: N815 - external eval schema field
    fl_conditioned_repair_correct: bool = False
    repair_correct: bool = False
    gate_results: list[dict[str, Any]] = Field(default_factory=list)
    rds_features: RDSFeatureVector | None = None
    contamination_flag: str = "unknown"
    flaky_flag: bool = False
    wall_ms: int = 0
    token_count: int = 0
    budget_events: list[str] = Field(default_factory=list)
    incident_ids: list[str] = Field(default_factory=list)
    notes: str | None = None


class OperationalQualityMetrics(StrictEvalModel):
    eval_run_id: str
    process_compliance_rate: float
    trace_replay_success_rate: float
    policy_violation_count: int = 0
    budget_hard_stop_count: int = 0
    incident_recidivism_rate: float = 0.0
    promotion_precision_placeholder: float = 0.0
    cost_per_accepted_verdict: float = 0.0
    readiness_delta: float = 0.0
    computed_ts: str = Field(default_factory=now_ts)


class EvalRun(StrictEvalModel):
    eval_run_id: str = Field(default_factory=new_eval_run_id)
    suite_id: str
    suite_version: str
    suite_median_age_days: float
    target_workflow: str
    target_tool: str
    model_backend: str
    toolset_hash: str
    policy_id: str
    permission_profile: str
    harness_condition_id: str
    start_ts: str = Field(default_factory=now_ts)
    end_ts: str | None = None
    status: EvalStatus = EvalStatus.running
    instance_count: int
    instance_results_ref: str | None = None
    aggregate_metrics_ref: str | None = None
    rds_summary_ref: str | None = None
    operational_metrics_ref: str | None = None
    contamination_canary_result: ContaminationCanaryResult
    freshness_check_ts: str = Field(default_factory=now_ts)
    artefact_manifest_ref: str
    run_record_id: str | None = None
    notes: str | None = None
    fl_metrics: dict[str, Any] = Field(default_factory=dict)
    operational_metrics: OperationalQualityMetrics | None = None
    manifest_regression: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _requires_harness_condition(self) -> EvalRun:
        if not self.harness_condition_id:
            raise ValueError("harness_condition_id is required")
        return self


class MaintainabilityOracleResult(StrictEvalModel):
    oracle_run_id: str
    diff_id: str
    change_locality_score: float
    dependency_direction_pass: bool
    responsibility_pass: bool
    reuse_pass: bool
    side_effect_pass: bool
    testability_pass: bool
    overall_pass: bool
    findings: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    computed_ts: str = Field(default_factory=now_ts)


class AIReadinessReport(StrictEvalModel):
    report_id: str
    repo_id: str
    eval_run_id: str
    harness_stage: str
    agent_config_score: int
    documentation_score: int
    ci_cd_score: int
    code_structure_score: int
    security_score: int
    total_score: int
    stage_threshold_met: bool
    axis_findings: dict[str, str]
    readiness_delta_from_last: int = 0
    no_regression_check_pass: bool = True
    computed_ts: str = Field(default_factory=now_ts)


class FlakyTestRecord(StrictEvalModel):
    instance_id: str
    eval_run_id: str
    flaky_flag: bool
    entropy_score: float
    rerun_count: int
    pass_count: int
    fail_count: int
    detection_method: str
    excluded_from_aggregate: bool


class ManifestRegressionResult(StrictEvalModel):
    run_id: str
    eval_run_id: str
    scope: str
    changed_items: list[str] = Field(default_factory=list)
    findings: list[dict[str, str]] = Field(default_factory=list)
    overall_verdict: str
    computed_ts: str = Field(default_factory=now_ts)
