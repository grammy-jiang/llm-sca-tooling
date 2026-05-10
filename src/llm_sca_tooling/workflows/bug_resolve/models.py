"""Pydantic v2 models for Phase 13 bug-resolve workflow."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, id_field


class StageName(StrEnum):
    LOAD = "load"
    INVESTIGATE = "investigate"
    REPAIR = "repair"
    DRYRUN = "dryrun"
    GATES = "gates"
    PATCH_RISK = "patch_risk"
    BLAST_RADIUS = "blast_radius"
    SCOPE_AUDIT = "scope_audit"
    OPERATIONAL_REVIEW = "operational_review"
    TRAJECTORY = "trajectory"


class StatusValue(StrEnum):
    RUNNING = "running"
    COMPLETED_SUCCESS = "completed_success"
    COMPLETED_NO_FIX = "completed_no_fix"
    COMPLETED_UNCERTAIN = "completed_uncertain"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BUDGET_EXHAUSTED = "budget_exhausted"


class FinalVerdict(StrEnum):
    RESOLVED = "resolved"
    RESOLVED_WITH_RISK = "resolved_with_risk"
    NO_FIX_FOUND = "no_fix_found"
    UNCERTAIN = "uncertain"
    PROCESS_NONCOMPLIANT = "process_noncompliant"
    BUDGET_EXHAUSTED = "budget_exhausted"


class RecommendationValue(StrEnum):
    MERGE_SUPPORTING = "merge-supporting"
    REVIEW_REQUIRED = "review-required"
    BLOCK = "block"
    UNKNOWN = "unknown"


class CertificateConclusion(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class TestExecResult(StrEnum):
    __test__ = False  # not a pytest test class

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    NOT_EXECUTED = "not_executed"
    FLAKY = "flaky"


class MonitorType(StrEnum):
    DOOM_LOOP_CANDIDATE = "doom_loop_candidate"
    REPEATED_FAILING_GATE = "repeated_failing_gate"
    CONTEXT_BUDGET_HARD_STOP = "context_budget_hard_stop"
    TOKEN_BUDGET_HARD_STOP = "token_budget_hard_stop"
    WALL_CLOCK_BUDGET_HARD_STOP = "wall_clock_budget_hard_stop"
    STALE_SNAPSHOT_DETECTED_BEFORE_FINAL_REPORT = (
        "stale_snapshot_detected_before_final_report"
    )


class InvestigateResult(StrictBaseModel):
    run_id: str = Field(min_length=1)
    issue_text_hash: str = Field(min_length=1)
    localisation_result_ref: str | None = None
    ranked_candidates: list[JsonObject] = Field(default_factory=list)
    top3_file_suspects: list[str] = Field(default_factory=list)
    repo_qa_answers: list[JsonObject] = Field(default_factory=list)
    behavioural_context: list[str] = Field(default_factory=list)
    agreement_score: float = Field(default=0.0, ge=0.0, le=1.0)
    budget_used: JsonObject = Field(default_factory=dict)
    snapshot_id: str | None = None
    stale_snapshot_flag: bool = False
    confidence: str = "unknown"
    diagnostics: list[JsonObject] = Field(default_factory=list)


class RepairContextRecord(StrictBaseModel):
    run_id: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)
    file_suspects: list[str] = Field(default_factory=list)
    graph_slices_ref: list[str] = Field(default_factory=list)
    summaries_ref: list[str] = Field(default_factory=list)
    blame_chain_refs: list[str] = Field(default_factory=list)
    sarif_alerts_in_scope: list[str] = Field(default_factory=list)
    interface_contracts_ref: list[str] = Field(default_factory=list)
    snapshot_id: str | None = None
    language: str | None = None
    context_tokens_estimate: int = Field(default=0, ge=0)
    budget_remaining: int = Field(default=0, ge=0)
    provenance: JsonObject = Field(default_factory=dict)


class CandidatePatch(StrictBaseModel):
    run_id: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)
    diff_text: str = ""
    diff_format: str = Field(default="unified", min_length=1)
    changed_files: list[str] = Field(default_factory=list)
    changed_symbol_ids: list[str] = Field(default_factory=list)
    generation_method: str = Field(default="null-adapter", min_length=1)
    generator_model: str | None = None
    reasoning_chain: str = ""
    certificate_ref: str | None = None
    precondition_draft_ref: str | None = None
    postcondition_draft_ref: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    provenance: JsonObject = Field(default_factory=dict)


class PrePostConditionDraft(StrictBaseModel):
    run_id: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)
    function_path: str = Field(min_length=1)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    generation_method: str = Field(default="null-adapter", min_length=1)
    confidence: str = "unknown"


class ReproductionTestRecord(StrictBaseModel):
    run_id: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)
    test_code: str = ""
    test_file: str | None = None
    generation_method: str = Field(default="null-adapter", min_length=1)
    pre_fix_result: TestExecResult = TestExecResult.NOT_EXECUTED
    post_fix_result: TestExecResult = TestExecResult.NOT_EXECUTED
    fails_for_expected_reason: bool = False
    flaky_flag: bool = False
    flaky_entropy_score: float = Field(default=0.0, ge=0.0, le=1.0)
    generated_test_is_hard_evidence: bool = False
    diagnostics: list[JsonObject] = Field(default_factory=list)


class ExecutionFreeCertificate(StrictBaseModel):
    run_id: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)
    definitions: list[str] = Field(default_factory=list)
    premises: list[str] = Field(default_factory=list)
    path_claims: list[str] = Field(default_factory=list)
    counterexample_search: str = ""
    conclusion: CertificateConclusion = CertificateConclusion.UNKNOWN
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    unsupported_claims: list[str] = Field(default_factory=list)


class GateRunnerResult(StrictBaseModel):
    run_id: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)
    sarif_gate_pass: bool | None = None
    sarif_delta_ref: str | None = None
    build_gate_pass: bool | None = None
    test_gate_pass: bool | None = None
    required_test_result: TestExecResult = TestExecResult.NOT_EXECUTED
    reproduction_test_result: TestExecResult = TestExecResult.NOT_EXECUTED
    poc_plus_result: TestExecResult = TestExecResult.NOT_EXECUTED
    interface_gate_pass: bool | None = None
    interface_compat_ref: str | None = None
    dynamic_trace_ref: str | None = None
    dynamic_trace_status: str | None = None
    certificate_conclusion: CertificateConclusion = CertificateConclusion.UNKNOWN
    overall_gate_pass: bool = False
    block_reasons: list[str] = Field(default_factory=list)


class PatchSelectionRecord(StrictBaseModel):
    run_id: str = Field(min_length=1)
    candidates_evaluated: int = Field(default=0, ge=0)
    selected_candidate_index: int | None = None
    selection_rationale: str = ""
    selection_criteria: list[str] = Field(default_factory=list)
    rejected_candidates: list[int] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)


class BlastRadiusStub(StrictBaseModel):
    run_id: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)
    changed_symbol_ids: list[str] = Field(default_factory=list)
    direct_callers: list[str] = Field(default_factory=list)
    downstream_tests: list[str] = Field(default_factory=list)
    interface_boundaries: list[str] = Field(default_factory=list)
    cross_language_candidates: list[str] = Field(default_factory=list)
    ambiguous_links: list[str] = Field(default_factory=list)
    confirmed_links: list[str] = Field(default_factory=list)
    local_impact_count: int = Field(default=0, ge=0)
    is_partial: bool = True
    diagnostics: list[JsonObject] = Field(default_factory=list)


class MonitorEvent(StrictBaseModel):
    run_id: str = Field(min_length=1)
    monitor_type: MonitorType
    stage: StageName
    loop_count: int = Field(default=0, ge=0)
    detail: str = ""
    severity: str = Field(default="warning", min_length=1)
    action_taken: str = Field(default="logged", min_length=1)


class WorkflowState(StrictBaseModel):
    run_id: str = Field(min_length=1)
    stage: StageName = StageName.LOAD
    stage_history: list[StageName] = Field(default_factory=list)
    investigate_result: InvestigateResult | None = None
    repair_candidates: list[CandidatePatch] = Field(default_factory=list)
    dryrun_predictions: list[JsonObject] = Field(default_factory=list)
    gate_results: list[GateRunnerResult] = Field(default_factory=list)
    patch_risk_results: list[JsonObject] = Field(default_factory=list)
    blast_radius_result: BlastRadiusStub | None = None
    scope_audit_result: JsonObject | None = None
    operational_verdict: str = "unknown"
    selected_patch: CandidatePatch | None = None
    final_report_ref: str | None = None
    status: StatusValue = StatusValue.RUNNING
    error: str | None = None
    loop_count: int = Field(default=0, ge=0)
    monitor_events: list[MonitorEvent] = Field(default_factory=list)


class BugResolveReport(StrictBaseModel):
    report_id: str = id_field("Bug-resolve report identifier.")
    run_id: str = Field(min_length=1)
    harness_condition_id: str = Field(min_length=1)
    issue_text_hash: str = Field(min_length=1)
    investigate_result_ref: str | None = None
    selected_patch_ref: str | None = None
    candidate_patches_ref: list[str] = Field(default_factory=list)
    precondition_draft_ref: str | None = None
    postcondition_draft_ref: str | None = None
    reproduction_tests_ref: list[str] = Field(default_factory=list)
    certificate_ref: str | None = None
    gate_results_ref: list[str] = Field(default_factory=list)
    patch_risk_result_ref: str | None = None
    blast_radius_result_ref: str | None = None
    scope_audit_result_ref: str | None = None
    patch_review_report_ref: str | None = None
    dryrun_prediction_ref: str | None = None
    dryrun_mismatches_ref: list[str] = Field(default_factory=list)
    operational_verdict: str = "unknown"
    incident_links: list[str] = Field(default_factory=list)
    final_verdict: FinalVerdict
    recommendation: RecommendationValue
    uncertainty: list[str] = Field(default_factory=list)
    session_trace_manifest_ref: str | None = None
    created_ts: str = Field(min_length=1)


class SessionTraceManifest(StrictBaseModel):
    run_id: str = Field(min_length=1)
    workflow: str = Field(default="bug-resolve", min_length=1)
    issue_text_hash: str = Field(min_length=1)
    repos: list[str] = Field(default_factory=list)
    start_ts: str = Field(min_length=1)
    end_ts: str = Field(min_length=1)
    stage_sequence: list[StageName] = Field(default_factory=list)
    artefact_refs: list[str] = Field(default_factory=list)
    tool_calls: list[JsonObject] = Field(default_factory=list)
    gate_events: list[JsonObject] = Field(default_factory=list)
    monitor_events: list[MonitorEvent] = Field(default_factory=list)
    budget_events: list[JsonObject] = Field(default_factory=list)
    approval_events: list[JsonObject] = Field(default_factory=list)
    redaction_policy: str = Field(default="redacted", min_length=1)
    harness_condition_id: str = Field(min_length=1)


__all__ = [
    "BlastRadiusStub",
    "BugResolveReport",
    "CandidatePatch",
    "CertificateConclusion",
    "ExecutionFreeCertificate",
    "FinalVerdict",
    "GateRunnerResult",
    "InvestigateResult",
    "MonitorEvent",
    "MonitorType",
    "PatchSelectionRecord",
    "PrePostConditionDraft",
    "RecommendationValue",
    "RepairContextRecord",
    "ReproductionTestRecord",
    "SessionTraceManifest",
    "StageName",
    "StatusValue",
    "TestExecResult",
    "WorkflowState",
]
