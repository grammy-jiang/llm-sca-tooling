"""Pydantic contracts for governed trajectory memory."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, id_field
from llm_sca_tooling.storage.workspace import _now_ts


class MemoryDisabledReason(StrEnum):
    WORKSPACE_DISABLED = "workspace_disabled"
    REPO_DISABLED = "repo_disabled"


class RetentionClass(StrEnum):
    EPHEMERAL = "ephemeral"
    WORKSPACE_LOCAL = "workspace_local"
    LONG_TERM = "long_term"
    ARCHIVED = "archived"


class ReviewState(StrEnum):
    UNREVIEWED = "unreviewed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class ProjectMemoryRecordType(StrEnum):
    DECISION = "decision"
    CONSTRAINT = "constraint"
    ALLOWED_COMMAND = "allowed_command"
    COMPONENT = "component"
    INCIDENT = "incident"
    EXPLICIT_UNKNOWN = "explicit_unknown"
    REJECTED_OPTION = "rejected_option"


class TrajectoryOutcome(StrEnum):
    RESOLVED = "resolved"
    RESOLVED_WITH_RISK = "resolved_with_risk"
    NO_FIX_FOUND = "no_fix_found"
    REJECTED_BY_REVIEW = "rejected_by_review"
    FALSE_POSITIVE = "false_positive"
    UNCERTAIN = "uncertain"
    RELABELLED = "relabelled"


class TrajectoryUtility(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class HintType(StrEnum):
    FL_DECISION = "fl_decision"
    PATCH_SNIPPET = "patch_snippet"
    PREDICATE_EXAMPLE = "predicate_example"
    RISK_PATTERN = "risk_pattern"
    TEST_HINT = "test_hint"
    REJECTION_REASON = "rejection_reason"


class LessonTargetType(StrEnum):
    MEMORY = "memory"
    DETECTOR = "detector"
    EVAL_REGRESSION = "eval_regression"
    STATIC_ANALYSIS_RULE = "static_analysis_rule"
    READINESS_TASK = "readiness_task"
    GOVERNANCE_POLICY = "governance_policy"


class MemoryOptInPolicy(StrictBaseModel):
    workspace_id: str = Field(min_length=1)
    enabled: bool = False
    per_repo_overrides: dict[str, bool] = Field(default_factory=dict)
    retention_class_default: RetentionClass = RetentionClass.WORKSPACE_LOCAL
    max_trajectory_count: int = Field(default=500, ge=1)
    max_project_memory_records: int = Field(default=200, ge=1)
    allow_snippet_storage: bool = False
    max_snippet_bytes: int = Field(default=2048, ge=0, le=16_384)
    allow_hindsight_relabelling: bool = False
    allow_operational_lesson_promotion: bool = False
    secret_scan_required: bool = True
    pii_redaction_required: bool = True
    review_required_for_promotion: bool = True
    opt_in_ts: str | None = None
    opt_in_actor: str | None = None

    @model_validator(mode="after")
    def validate_non_relaxable_defaults(self) -> MemoryOptInPolicy:
        if not self.secret_scan_required:
            raise ValueError("secret_scan_required cannot be disabled")
        if not self.review_required_for_promotion:
            raise ValueError("review_required_for_promotion cannot be disabled")
        if self.enabled and (not self.opt_in_ts or not self.opt_in_actor):
            raise ValueError("enabled memory requires opt_in_ts and opt_in_actor")
        return self

    def repo_enabled(self, repo_id: str) -> bool:
        return self.enabled and self.per_repo_overrides.get(repo_id, True)


class PrivacyRetentionFields(StrictBaseModel):
    retention_class: RetentionClass = RetentionClass.WORKSPACE_LOCAL
    expiry_ts: str | None = None
    source_run_id: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    export_permitted: bool = False
    delete_on_request: bool = True
    rollback_path: str = Field(min_length=1)
    bounded_snippets_only: bool = True
    raw_prompt_excluded: bool = True
    full_trace_excluded: bool = True
    command_output_excluded: bool = True
    full_source_excluded: bool = True


class ProjectMemoryRecord(StrictBaseModel):
    record_id: str = id_field("Project memory record identifier.")
    repo_id: str = Field(min_length=1)
    record_type: ProjectMemoryRecordType
    content_structured: JsonObject
    source_run_id: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    retention_class: RetentionClass = RetentionClass.WORKSPACE_LOCAL
    expiry_ts: str | None = None
    review_state: ReviewState = ReviewState.UNREVIEWED
    contradiction_check_ts: str | None = None
    rollback_path: str = Field(min_length=1)
    created_ts: str = Field(default_factory=_now_ts)
    updated_ts: str = Field(default_factory=_now_ts)

    @field_validator("content_structured")
    @classmethod
    def validate_structured_content(cls, value: JsonObject) -> JsonObject:
        if not value:
            raise ValueError("content_structured must be non-empty")
        prose_only_keys = {"text", "lesson", "note", "content"}
        if set(value) <= prose_only_keys:
            raise ValueError(
                "project memory requires structured fields, not prose only"
            )
        return value


class TrajectoryRecord(StrictBaseModel):
    trajectory_id: str = id_field("Trajectory identifier.")
    repo_id: str = Field(min_length=1)
    workflow_type: str = Field(min_length=1)
    issue_class: str = Field(min_length=1)
    issue_text_hash: str = Field(min_length=1)
    fl_decisions: list[JsonObject] = Field(default_factory=list)
    graph_node_ids: list[str] = Field(default_factory=list)
    graph_snapshot_id: str = Field(min_length=1)
    patch_diff_hash: str | None = None
    patch_class: str | None = None
    sarif_delta_summary: JsonObject = Field(default_factory=dict)
    test_delta_summary: JsonObject = Field(default_factory=dict)
    outcome: TrajectoryOutcome = TrajectoryOutcome.UNCERTAIN
    utility: TrajectoryUtility = TrajectoryUtility.UNKNOWN
    hindsight_label: str | None = None
    hindsight_label_confidence: str = "unknown"
    relabelled: bool = False
    source_run_id: str = Field(min_length=1)
    source_trace_manifest_id: str | None = None
    retention_class: RetentionClass = RetentionClass.WORKSPACE_LOCAL
    expiry_ts: str | None = None
    review_state: ReviewState = ReviewState.UNREVIEWED
    bounded_snippet_ids: list[str] = Field(default_factory=list)
    rollback_path: str = Field(default="delete trajectory record", min_length=1)
    created_ts: str = Field(default_factory=_now_ts)


class WritePathResult(StrictBaseModel):
    trajectory_id: str | None = None
    gates_passed: bool = False
    gate_failures: list[str] = Field(default_factory=list)
    secret_detected: bool = False
    contradiction_detected: bool = False
    contradiction_detail: str = ""
    review_state_set: ReviewState = ReviewState.UNREVIEWED
    written: bool = False
    diagnostics: list[JsonObject] = Field(default_factory=list)


class CoarseHint(StrictBaseModel):
    trajectory_id: str = Field(min_length=1)
    issue_class: str = Field(min_length=1)
    outcome: TrajectoryOutcome
    utility: TrajectoryUtility
    fl_class_match: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rejected: bool = False
    rejection_reason: str = ""


class FineHint(StrictBaseModel):
    trajectory_id: str = Field(min_length=1)
    hint_type: HintType
    content_snippet: str = ""
    graph_node_ids: list[str] = Field(default_factory=list)
    patch_class: str | None = None
    outcome: TrajectoryOutcome
    utility: TrajectoryUtility
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    misalignment_flag: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class HindsightLabel(StrictBaseModel):
    trajectory_id: str = Field(min_length=1)
    original_outcome: TrajectoryOutcome
    relabelled_goal: str = Field(min_length=1)
    relabelled_outcome: TrajectoryOutcome = TrajectoryOutcome.RELABELLED
    relabelled_utility: TrajectoryUtility = TrajectoryUtility.MEDIUM
    confidence: str = "unknown"
    evidence_refs: list[str] = Field(default_factory=list)
    generator_model: str = "null"
    review_state: ReviewState = ReviewState.UNREVIEWED


class EvictionPolicy(StrictBaseModel):
    max_trajectories_per_repo: int = Field(default=500, ge=1)
    max_project_memory_per_repo: int = Field(default=200, ge=1)
    utility_threshold_keep: float = Field(default=0.70, ge=0.0, le=1.0)
    utility_threshold_demote: float = Field(default=0.25, ge=0.0, le=1.0)
    recency_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    outcome_diversity_target: int = Field(default=3, ge=1)
    issue_class_coverage_target: int = Field(default=5, ge=1)
    relabelled_penalty: float = Field(default=0.10, ge=0.0, le=1.0)
    expiry_default_days: int = Field(default=180, ge=1)
    compaction_batch_size: int = Field(default=100, ge=1)


class MemoryCompactionReport(StrictBaseModel):
    report_id: str = Field(min_length=1)
    repo_id: str | None = None
    dry_run: bool = True
    initial_count: int = Field(ge=0)
    promoted_count: int = Field(default=0, ge=0)
    demoted_count: int = Field(default=0, ge=0)
    expired_count: int = Field(default=0, ge=0)
    final_count: int = Field(ge=0)
    utility_distribution: dict[str, int] = Field(default_factory=dict)
    outcome_diversity_achieved: int = Field(default=0, ge=0)
    issue_class_coverage_achieved: int = Field(default=0, ge=0)
    updated_trajectory_ids: list[str] = Field(default_factory=list)
    created_ts: str = Field(default_factory=_now_ts)


class OperationalLesson(StrictBaseModel):
    lesson_id: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    trigger_condition: str = Field(min_length=1)
    lesson_type: str = Field(min_length=1)
    structured_content: JsonObject
    target_type: LessonTargetType
    owner: str = Field(min_length=1)
    expiry_ts: str | None = None
    review_date: str = Field(min_length=1)
    rollback_path: str = Field(min_length=1)
    review_state: ReviewState = ReviewState.UNREVIEWED
    promoted_to_ref: str | None = None
    created_ts: str = Field(default_factory=_now_ts)


class MemoryShipGateResult(StrictBaseModel):
    eval_run_id: str = Field(min_length=1)
    strategy_tested: str = Field(min_length=1)
    baseline_strategy: str = Field(min_length=1)
    pass_rate_strategy: float = Field(ge=0.0, le=1.0)
    pass_rate_baseline: float = Field(ge=0.0, le=1.0)
    delta_pp: float
    gate_passed: bool
    context_budget_used: int = Field(ge=0)
    harness_condition_id: str = Field(min_length=1)
    computed_ts: str = Field(default_factory=_now_ts)
    memory_hint_weight: float = Field(default=0.0, ge=0.0, le=1.0)
