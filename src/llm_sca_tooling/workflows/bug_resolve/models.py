"""Phase 13 bug-resolve workflow models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm_sca_tooling.evaluation.models import now_ts


class StrictWorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Config ──────────────────────────────────────────────────────────────────


class WorkflowConfig(StrictWorkflowModel):
    max_candidates: int = 3
    max_repair_loops: int = 5
    max_gate_retries: int = 2
    context_budget: int = 8000
    token_budget: int = 200_000
    wall_clock_budget_seconds: int = 1800
    fl_budget: int = 4000
    require_reproduction_test: bool = True
    require_blast_radius: bool = True
    require_patch_review: bool = True
    require_sarif_gate: bool = True
    require_interface_gate: bool = True
    null_mode: bool = False
    permission_profile: str = "default"
    policy_id: str = "default"
    sandbox_only: bool = True


# ── State machine ────────────────────────────────────────────────────────────


class WorkflowState(StrictWorkflowModel):
    run_id: str
    stage: str = "load"
    stage_history: list[str] = Field(default_factory=list)
    investigate_result: dict[str, Any] | None = None
    repair_candidates: list[dict[str, Any]] = Field(default_factory=list)
    dryrun_predictions: list[dict[str, Any]] = Field(default_factory=list)
    gate_results: list[dict[str, Any]] = Field(default_factory=list)
    patch_risk_results: list[dict[str, Any]] = Field(default_factory=list)
    blast_radius_result: dict[str, Any] | None = None
    scope_audit_result: dict[str, Any] | None = None
    operational_verdict: str = "unknown"
    selected_patch: dict[str, Any] | None = None
    final_report_ref: str | None = None
    status: str = "running"
    error: str | None = None
    loop_count: int = 0
    monitor_events: list[dict[str, Any]] = Field(default_factory=list)


# ── Investigate ──────────────────────────────────────────────────────────────


class InvestigateResult(StrictWorkflowModel):
    run_id: str
    issue_text_hash: str
    localisation_result_ref: str
    ranked_candidates: list[dict[str, Any]] = Field(default_factory=list)
    top3_file_suspects: list[str] = Field(default_factory=list)
    repo_qa_answers: list[dict[str, Any]] = Field(default_factory=list)
    behavioural_context: str = ""
    agreement_score: float = 0.0
    budget_used: int = 0
    snapshot_id: str | None = None
    stale_snapshot_flag: bool = False
    confidence: str = "unknown"
    diagnostics: list[str] = Field(default_factory=list)


# ── Repair ───────────────────────────────────────────────────────────────────


class RepairContextRecord(StrictWorkflowModel):
    run_id: str
    candidate_index: int
    file_suspects: list[str] = Field(default_factory=list)
    graph_slices_ref: str
    summaries_ref: str
    blame_chain_refs: list[str] = Field(default_factory=list)
    sarif_alerts_in_scope: list[dict[str, Any]] = Field(default_factory=list)
    interface_contracts_ref: str | None = None
    snapshot_id: str | None = None
    language: str = "python"
    context_tokens_estimate: int = 0
    budget_remaining: int = 0
    provenance: dict[str, Any] = Field(default_factory=dict)


class CandidatePatch(StrictWorkflowModel):
    run_id: str
    candidate_index: int
    diff_text: str
    diff_format: str = "unified"
    changed_files: list[str] = Field(default_factory=list)
    changed_symbol_ids: list[str] = Field(default_factory=list)
    generation_method: str
    generator_model: str
    reasoning_chain: list[str] = Field(default_factory=list)
    certificate_ref: str | None = None
    precondition_draft_ref: str | None = None
    postcondition_draft_ref: str | None = None
    confidence: str = "unknown"
    provenance: dict[str, Any] = Field(default_factory=dict)


class PrePostConditionDraft(StrictWorkflowModel):
    run_id: str
    candidate_index: int
    function_path: str
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    generation_method: str = "null"
    confidence: str = "unknown"


# ── Reproduction test ────────────────────────────────────────────────────────


class ReproductionTestRecord(StrictWorkflowModel):
    run_id: str
    candidate_index: int
    test_code: str
    test_file: str
    generation_method: str = "assertflip"
    pre_fix_result: str = "not_executed"
    post_fix_result: str = "not_executed"
    fails_for_expected_reason: bool = False
    flaky_flag: bool = False
    flaky_entropy_score: float = 0.0
    generated_test_is_hard_evidence: bool = False
    diagnostics: list[str] = Field(default_factory=list)


# ── Certificate ──────────────────────────────────────────────────────────────


class ExecutionFreeCertificate(StrictWorkflowModel):
    run_id: str
    candidate_index: int
    definitions: list[str] = Field(default_factory=list)
    premises: list[str] = Field(default_factory=list)
    path_claims: list[str] = Field(default_factory=list)
    counterexample_search: str = "not_run"
    conclusion: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: str = "unknown"
    unsupported_claims: list[str] = Field(default_factory=list)


# ── Gate runner ───────────────────────────────────────────────────────────────


class GateRunnerResult(StrictWorkflowModel):
    run_id: str
    candidate_index: int
    sarif_gate_pass: bool = True
    sarif_delta_ref: str | None = None
    build_gate_pass: bool = True
    test_gate_pass: bool = True
    required_test_result: str = "not_executed"
    reproduction_test_result: str = "not_executed"
    poc_plus_result: str = "not_applicable"
    interface_gate_pass: bool = True
    interface_compat_ref: str | None = None
    certificate_conclusion: str = "unknown"
    overall_gate_pass: bool = True
    block_reasons: list[str] = Field(default_factory=list)


# ── Patch selection ───────────────────────────────────────────────────────────


class PatchSelectionRecord(StrictWorkflowModel):
    run_id: str
    candidates_evaluated: int
    selected_candidate_index: int | None = None
    selection_rationale: str
    selection_criteria: list[str] = Field(default_factory=list)
    rejected_candidates: list[int] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)


# ── Blast radius ─────────────────────────────────────────────────────────────


class BlastRadiusStub(StrictWorkflowModel):
    run_id: str
    candidate_index: int
    changed_symbol_ids: list[str] = Field(default_factory=list)
    direct_callers: list[str] = Field(default_factory=list)
    downstream_tests: list[str] = Field(default_factory=list)
    interface_boundaries: list[str] = Field(default_factory=list)
    cross_language_candidates: list[str] = Field(default_factory=list)
    ambiguous_links: list[str] = Field(default_factory=list)
    confirmed_links: list[str] = Field(default_factory=list)
    local_impact_count: int = 0
    is_partial: bool = True
    diagnostics: list[str] = Field(default_factory=list)


# ── Monitor hooks ─────────────────────────────────────────────────────────────


class MonitorEvent(StrictWorkflowModel):
    run_id: str
    monitor_type: str
    stage: str
    loop_count: int = 0
    detail: str = ""
    severity: str = "warning"
    action_taken: str = "logged"


# ── Final report ──────────────────────────────────────────────────────────────


class BugResolveReport(StrictWorkflowModel):
    report_id: str
    run_id: str
    harness_condition_id: str
    issue_text_hash: str
    investigate_result_ref: str
    selected_patch_ref: str | None = None
    candidate_patches_ref: str
    precondition_draft_ref: str
    postcondition_draft_ref: str
    reproduction_tests_ref: str
    certificate_ref: str
    gate_results_ref: str
    patch_risk_result_ref: str
    blast_radius_result_ref: str
    scope_audit_result_ref: str
    patch_review_report_ref: str | None = None
    dryrun_prediction_ref: str
    dryrun_mismatches_ref: str
    operational_verdict: str = "unknown"
    incident_links: list[str] = Field(default_factory=list)
    final_verdict: str
    recommendation: str
    uncertainty: str = ""
    session_trace_manifest_ref: str
    created_ts: str = Field(default_factory=now_ts)


# ── Trace manifest ────────────────────────────────────────────────────────────


class SessionTraceManifest(StrictWorkflowModel):
    run_id: str
    workflow: str = "bug-resolve"
    issue_text_hash: str
    repos: list[str] = Field(default_factory=list)
    start_ts: str
    end_ts: str
    stage_sequence: list[str] = Field(default_factory=list)
    artefact_refs: list[str] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    gate_events: list[str] = Field(default_factory=list)
    monitor_events: list[str] = Field(default_factory=list)
    budget_events: list[str] = Field(default_factory=list)
    approval_events: list[str] = Field(default_factory=list)
    redaction_policy: str = "default"
    harness_condition_id: str
