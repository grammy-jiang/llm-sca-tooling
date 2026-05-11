"""Phase 14 implementation-check models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm_sca_tooling.evaluation.models import now_ts


class StrictImplModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Stage 1 ───────────────────────────────────────────────────────────────────


class SpecDocument(StrictImplModel):
    doc_id: str
    source_path: str
    doc_format: str = "markdown"
    title: str
    content_hash: str
    ingested_ts: str = Field(default_factory=now_ts)
    clause_count: int = 0
    provenance: dict[str, Any] = Field(default_factory=dict)


class Clause(StrictImplModel):
    clause_id: str
    doc_id: str
    text: str
    source_span: tuple[int, int]
    scope: str = "module"
    priority: str = "must"
    checkability: str = "static"
    target_candidates: list[str] = Field(default_factory=list)
    risk_class: str = "correctness"
    rejected_interpretations: list[str] = Field(default_factory=list)
    parent_clause_id: str | None = None
    atomic: bool = True
    harness_policy_flag: bool = False


class HarnessPolicyClause(StrictImplModel):
    clause_id: str
    doc_id: str
    text: str
    source_span: tuple[int, int]
    risk_class: str = "compliance"
    harness_policy_flag: bool = True
    atomic: bool = True
    policy_source: str
    enforcement_mechanism: str
    checked_by_tool: str
    harness_stage_required: str
    target_candidates: list[str] = Field(default_factory=list)
    checkability: str = "static"


# ── Stage 2 ───────────────────────────────────────────────────────────────────


class IntentNode(StrictImplModel):
    node_id: str
    clause_id: str
    text_summary: str
    target_symbol_ids: list[str] = Field(default_factory=list)
    evidence_node_ids: list[str] = Field(default_factory=list)
    confidence: str = "heuristic"


class IntentGraph(StrictImplModel):
    graph_id: str
    doc_id: str
    clause_ids: list[str] = Field(default_factory=list)
    intent_nodes: list[IntentNode] = Field(default_factory=list)
    decomposes_to_edges: list[tuple[str, str]] = Field(default_factory=list)
    satisfies_edges: list[tuple[str, str]] = Field(default_factory=list)
    violates_edges: list[tuple[str, str]] = Field(default_factory=list)
    checks_edges: list[tuple[str, str]] = Field(default_factory=list)
    snapshot_id: str | None = None
    created_ts: str = Field(default_factory=now_ts)


# ── Stage 3 ───────────────────────────────────────────────────────────────────


class ImplContractArtifact(StrictImplModel):
    artifact_id: str
    clause_id: str
    language: str
    artifact_type: str
    target_symbols: list[str] = Field(default_factory=list)
    source_clause_span: tuple[int, int] | None = None
    compile_status: str = "not_attempted"
    last_run_status: str = "not_run"
    confidence: float = 0.0
    content: str = ""


# ── Stage 4 ───────────────────────────────────────────────────────────────────


class ClauseGrounding(StrictImplModel):
    clause_id: str
    grounding_method: str
    symbol_node_ids: list[str] = Field(default_factory=list)
    file_node_ids: list[str] = Field(default_factory=list)
    graph_slice_refs: list[str] = Field(default_factory=list)
    interface_contract_ids: list[str] = Field(default_factory=list)
    document_link_node_ids: list[str] = Field(default_factory=list)
    repo_qa_answer_refs: list[str] = Field(default_factory=list)
    confidence: str = "unknown"
    ungrounded_reason: str | None = None


# ── Stage 5 / 6a ─────────────────────────────────────────────────────────────


class StaticVerdictRecord(StrictImplModel):
    clause_id: str
    stage: str
    verdict: str
    evidence_type: str
    contract_artifact_id: str | None = None
    sarif_alert_ids: list[str] = Field(default_factory=list)
    test_result_ids: list[str] = Field(default_factory=list)
    graph_path_evidence: list[str] = Field(default_factory=list)
    confidence: str = "unknown"
    ece_bucket: str = "unknown"
    override_reason: str | None = None


# ── Stage 6b ─────────────────────────────────────────────────────────────────


class DynamicVerdictRecord(StrictImplModel):
    clause_id: str
    stage: str = "6b"
    trace_run_id: str | None = None
    compressed_trace_ref: str | None = None
    verdict: str = "unknown"
    divergence_points: list[str] = Field(default_factory=list)
    confidence: str = "unknown"
    available: bool = False


# ── Stage 7 ───────────────────────────────────────────────────────────────────


class ClauseVerdictRecord(StrictImplModel):
    clause_id: str
    final_verdict: str
    confidence: str
    ece_bucket: str
    stage_5_verdicts: list[str] = Field(default_factory=list)
    stage_6a_verdicts: list[str] = Field(default_factory=list)
    stage_6b_verdict: str | None = None
    dominant_evidence: str
    aggregation_method: str = "priority_dominance"
    auto_pass_gate_passed: bool = False
    calibration_family: str = "unknown"
    uncertainty_reason: str | None = None


class ClauseVerdictMatrix(StrictImplModel):
    doc_id: str
    run_id: str
    clause_count: int
    satisfied_count: int
    violated_count: int
    unknown_count: int
    security_clause_verdicts: list[dict[str, Any]] = Field(default_factory=list)
    harness_policy_verdicts: list[dict[str, Any]] = Field(default_factory=list)
    per_clause_records: list[ClauseVerdictRecord] = Field(default_factory=list)
    overall_compliance_status: str
    created_ts: str = Field(default_factory=now_ts)


# ── Operational binding ───────────────────────────────────────────────────────


class OperationalEvidenceBinding(StrictImplModel):
    run_id: str
    clause_id: str
    graph_snapshot_id: str | None = None
    resource_refs: list[str] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    gate_results: list[str] = Field(default_factory=list)
    stale_snapshot_flag: bool = False
    mixed_snapshot_flag: bool = False
    required_gate_events_present: bool = True
    harness_condition_id: str


# ── Final report ──────────────────────────────────────────────────────────────


class ImplementationCheckReport(StrictImplModel):
    report_id: str
    run_id: str
    harness_condition_id: str
    doc_id: str
    spec_document_ref: str
    intent_graph_ref: str
    clause_verdict_matrix_ref: str
    violated_clauses: list[str] = Field(default_factory=list)
    unknown_clauses: list[str] = Field(default_factory=list)
    satisfied_clauses: list[str] = Field(default_factory=list)
    security_clause_summary: str = "none"
    harness_policy_summary: str = "none"
    operational_compliance_verdict: str = "unknown"
    manifest_regression_verdict: str = "not_run"
    overall_verdict: str
    recommendation: str
    uncertainty: str = ""
    session_trace_manifest_ref: str
    created_ts: str = Field(default_factory=now_ts)
