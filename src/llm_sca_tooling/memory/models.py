"""Phase 17 memory models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm_sca_tooling.evaluation.models import now_ts


class StrictMemoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Opt-in policy ─────────────────────────────────────────────────────────────


class MemoryOptInPolicy(StrictMemoryModel):
    workspace_id: str
    enabled: bool = False
    per_repo_overrides: dict[str, bool] = Field(default_factory=dict)
    retention_class_default: str = "workspace_local"
    max_trajectory_count: int = 500
    max_project_memory_records: int = 100
    allow_snippet_storage: bool = True
    max_snippet_bytes: int = 4096
    allow_hindsight_relabelling: bool = False
    allow_operational_lesson_promotion: bool = False
    secret_scan_required: bool = True
    pii_redaction_required: bool = True
    review_required_for_promotion: bool = True
    opt_in_ts: str | None = None
    opt_in_actor: str | None = None


# ── Project memory ────────────────────────────────────────────────────────────


class ProjectMemoryRecord(StrictMemoryModel):
    record_id: str
    repo_id: str
    record_type: str
    content_structured: dict[str, Any]
    source_run_id: str
    source_event_id: str | None = None
    owner: str = "unknown"
    retention_class: str = "workspace_local"
    expiry_ts: str | None = None
    review_state: str = "unreviewed"
    contradiction_check_ts: str | None = None
    rollback_path: str | None = None
    created_ts: str = Field(default_factory=now_ts)
    updated_ts: str = Field(default_factory=now_ts)


# ── Trajectory record ─────────────────────────────────────────────────────────


class PrivacyRetentionFields(StrictMemoryModel):
    retention_class: str = "workspace_local"
    expiry_ts: str | None = None
    source_run_id: str
    owner: str = "unknown"
    export_permitted: bool = False
    delete_on_request: bool = True
    rollback_path: str | None = None
    bounded_snippets_only: bool = True
    raw_prompt_excluded: bool = True
    full_trace_excluded: bool = True
    command_output_excluded: bool = True
    full_source_excluded: bool = True


class TrajectoryRecord(StrictMemoryModel):
    trajectory_id: str
    repo_id: str
    workflow_type: str
    issue_class: str
    issue_text_hash: str
    fl_decisions: list[str] = Field(default_factory=list)
    graph_node_ids: list[str] = Field(default_factory=list)
    graph_snapshot_id: str | None = None
    patch_diff_hash: str | None = None
    patch_class: str | None = None
    sarif_delta_summary: str | None = None
    test_delta_summary: str | None = None
    outcome: str
    utility: str = "unknown"
    hindsight_label: str | None = None
    hindsight_label_confidence: str = "unknown"
    relabelled: bool = False
    source_run_id: str
    source_trace_manifest_id: str | None = None
    retention_class: str = "workspace_local"
    expiry_ts: str | None = None
    review_state: str = "unreviewed"
    bounded_snippet_ids: list[str] = Field(default_factory=list)
    created_ts: str = Field(default_factory=now_ts)


# ── Write-path ────────────────────────────────────────────────────────────────


class WritePathResult(StrictMemoryModel):
    trajectory_id: str
    gates_passed: list[str] = Field(default_factory=list)
    gate_failures: list[str] = Field(default_factory=list)
    secret_detected: bool = False
    contradiction_detected: bool = False
    contradiction_detail: str | None = None
    review_state_set: str = "unreviewed"
    written: bool = False


# ── Retrieval ─────────────────────────────────────────────────────────────────


class CoarseHint(StrictMemoryModel):
    trajectory_id: str
    issue_class: str
    outcome: str
    utility: str
    fl_class_match: bool = False
    confidence: str = "heuristic"
    rejected: bool = False
    rejection_reason: str | None = None


class FineHint(StrictMemoryModel):
    trajectory_id: str
    hint_type: str
    content_snippet: str
    graph_node_ids: list[str] = Field(default_factory=list)
    patch_class: str | None = None
    outcome: str
    utility: str
    similarity_score: float = 0.0
    misalignment_flag: bool = False
    confidence: str = "heuristic"


# ── Hindsight relabelling ─────────────────────────────────────────────────────


class HindsightLabel(StrictMemoryModel):
    trajectory_id: str
    original_outcome: str
    relabelled_goal: str
    relabelled_outcome: str
    relabelled_utility: str
    confidence: str = "unknown"
    evidence_refs: list[str] = Field(default_factory=list)
    generator_model: str = "null"
    review_state: str = "unreviewed"


# ── Eviction ─────────────────────────────────────────────────────────────────


class EvictionPolicy(StrictMemoryModel):
    max_trajectories_per_repo: int = 500
    max_project_memory_per_repo: int = 100
    utility_threshold_keep: float = 0.7
    utility_threshold_demote: float = 0.3
    recency_weight: float = 0.3
    outcome_diversity_target: int = 3
    issue_class_coverage_target: int = 5
    relabelled_penalty: float = 0.1
    expiry_default_days: int = 90
    compaction_batch_size: int = 50


class MemoryCompactionReport(StrictMemoryModel):
    repo_id: str
    initial_count: int
    promoted_count: int
    demoted_count: int
    expired_count: int
    final_count: int
    utility_distribution: dict[str, int] = Field(default_factory=dict)
    outcome_diversity_achieved: int = 0
    dry_run: bool = False
    created_ts: str = Field(default_factory=now_ts)


# ── Operational lesson ────────────────────────────────────────────────────────


class OperationalLesson(StrictMemoryModel):
    lesson_id: str
    source_run_id: str
    source_event_id: str | None = None
    trigger_condition: str
    lesson_type: str
    structured_content: dict[str, Any]
    target_type: str
    owner: str = "unknown"
    expiry_ts: str | None = None
    review_date: str | None = None
    rollback_path: str | None = None
    review_state: str = "unreviewed"
    promoted_to_ref: str | None = None
    created_ts: str = Field(default_factory=now_ts)


# ── Ship gate ─────────────────────────────────────────────────────────────────


class MemoryShipGateResult(StrictMemoryModel):
    eval_run_id: str
    strategy_tested: str = "her_plus_eviction"
    baseline_strategy: str = "success_only"
    pass_rate_strategy: float = 0.0
    pass_rate_baseline: float = 0.0
    delta_pp: float = 0.0
    gate_passed: bool = False
    context_budget_used: int = 0
    harness_condition_id: str
    computed_ts: str = Field(default_factory=now_ts)
