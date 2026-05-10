"""Phase 14 implementation-check Pydantic models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


class CheckabilityValue(StrEnum):
    STATIC = "static"
    DYNAMIC = "dynamic"
    HYBRID = "hybrid"
    STRUCTURAL = "structural"
    UNVERIFIABLE = "unverifiable"


class RiskClass(StrEnum):
    SECURITY = "security"
    CORRECTNESS = "correctness"
    PERFORMANCE = "performance"
    COMPATIBILITY = "compatibility"
    MAINTAINABILITY = "maintainability"
    COMPLIANCE = "compliance"
    UNKNOWN = "unknown"


class VerdictValue(StrEnum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


class CompileStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    NOT_ATTEMPTED = "not_attempted"


class ContractType(StrEnum):
    SEMGREP = "semgrep"
    CODEQL = "codeql"
    PYTEST = "pytest"
    UNIT_TEST = "unit_test"
    NATURAL_LANGUAGE_PROBE = "natural_language_probe"
    JML_LIKE = "jml_like"


class GroundingMethod(StrEnum):
    SYMBOL_MATCH = "symbol_match"
    DOCUMENT_LINK = "document_link"
    REPO_QA = "repo_qa"
    INTERFACE_CONTRACT = "interface_contract"
    UNGROUNDED = "ungrounded"


class EvidenceType(StrEnum):
    ANALYSER = "analyser"
    PARSER = "parser"
    TEST = "test"
    LLM = "llm"
    NONE = "none"


class ConfidenceLevel(StrEnum):
    ANALYSER = "analyser"
    PARSER = "parser"
    TEST = "test"
    LLM = "llm"
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"


class OverallComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    UNKNOWN = "unknown"


class OverallVerdict(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    UNKNOWN = "unknown"


class RecommendationValue(StrEnum):
    MERGE_SUPPORTING = "merge-supporting"
    REVIEW_REQUIRED = "review-required"
    BLOCK = "block"
    UNKNOWN = "unknown"


class AggregationMethod(StrEnum):
    HARD_VIOLATION_DOMINATES = "hard_violation_dominates"
    SOFT_CONSENSUS = "soft_consensus"
    AUTO_PASS = "auto_pass"
    DEFAULT_UNKNOWN = "default_unknown"


class SpecDocument(StrictBaseModel):
    doc_id: str = Field(min_length=1)
    source_path: str = ""
    doc_format: str = "markdown"
    title: str = ""
    content_hash: str = ""
    ingested_ts: str = ""
    clause_count: int = Field(default=0, ge=0)
    provenance: JsonObject = Field(default_factory=dict)


class Clause(StrictBaseModel):
    clause_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    text: str = ""
    source_span: str = ""
    scope: str = "general"
    priority: str = "normal"
    checkability: CheckabilityValue = CheckabilityValue.STATIC
    target_candidates: list[str] = Field(default_factory=list)
    risk_class: RiskClass = RiskClass.UNKNOWN
    rejected_interpretations: list[str] = Field(default_factory=list)
    parent_clause_id: str | None = None
    atomic: bool = True
    harness_policy_flag: bool = False


class HarnessPolicyClause(Clause):
    policy_source: str = ""
    enforcement_mechanism: str = ""
    checked_by_tool: str = ""
    harness_stage_required: str = ""


class IntentNode(StrictBaseModel):
    node_id: str = Field(min_length=1)
    clause_id: str = Field(min_length=1)
    text_summary: str = ""
    target_symbol_ids: list[str] = Field(default_factory=list)
    evidence_node_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class IntentGraph(StrictBaseModel):
    graph_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    clause_ids: list[str] = Field(default_factory=list)
    intent_nodes: list[IntentNode] = Field(default_factory=list)
    decomposes_to_edges: list[JsonObject] = Field(default_factory=list)
    satisfies_edges: list[JsonObject] = Field(default_factory=list)
    violates_edges: list[JsonObject] = Field(default_factory=list)
    checks_edges: list[JsonObject] = Field(default_factory=list)
    snapshot_id: str | None = None
    created_ts: str = ""


class ContractArtifact(StrictBaseModel):
    clause_id: str = Field(min_length=1)
    language: str = ""
    artifact_type: ContractType = ContractType.NATURAL_LANGUAGE_PROBE
    target_symbols: list[str] = Field(default_factory=list)
    source_clause_span: str = ""
    compile_status: CompileStatus = CompileStatus.NOT_ATTEMPTED
    last_run_status: VerdictValue = VerdictValue.UNKNOWN
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    content: str = ""


class ClauseGrounding(StrictBaseModel):
    clause_id: str = Field(min_length=1)
    grounding_method: GroundingMethod = GroundingMethod.UNGROUNDED
    symbol_node_ids: list[str] = Field(default_factory=list)
    file_node_ids: list[str] = Field(default_factory=list)
    graph_slice_refs: list[str] = Field(default_factory=list)
    interface_contract_ids: list[str] = Field(default_factory=list)
    document_link_node_ids: list[str] = Field(default_factory=list)
    repo_qa_answer_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ungrounded_reason: str = ""


class StaticVerdictRecord(StrictBaseModel):
    clause_id: str = Field(min_length=1)
    stage: str = "5"
    verdict: VerdictValue = VerdictValue.UNKNOWN
    evidence_type: EvidenceType = EvidenceType.NONE
    contract_artifact_id: str | None = None
    sarif_alert_ids: list[str] = Field(default_factory=list)
    test_result_ids: list[str] = Field(default_factory=list)
    graph_path_evidence: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    ece_bucket: str | None = None
    override_reason: str = ""


class DynamicVerdictRecord(StrictBaseModel):
    clause_id: str = Field(min_length=1)
    stage: str = "6b"
    trace_run_id: str | None = None
    compressed_trace_ref: str | None = None
    verdict: VerdictValue = VerdictValue.UNKNOWN
    divergence_points: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    available: bool = False


class ClauseVerdictRecord(StrictBaseModel):
    clause_id: str = Field(min_length=1)
    final_verdict: VerdictValue = VerdictValue.UNKNOWN
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    ece_bucket: str | None = None
    stage_5_verdicts: list[JsonObject] = Field(default_factory=list)
    stage_6a_verdicts: list[JsonObject] = Field(default_factory=list)
    stage_6b_verdict: JsonObject | None = None
    dominant_evidence: str = ""
    aggregation_method: AggregationMethod = AggregationMethod.DEFAULT_UNKNOWN
    auto_pass_gate_passed: bool = False
    calibration_family: str | None = None
    uncertainty_reason: str = ""


class ClauseVerdictMatrix(StrictBaseModel):
    doc_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    clause_count: int = Field(default=0, ge=0)
    satisfied_count: int = Field(default=0, ge=0)
    violated_count: int = Field(default=0, ge=0)
    unknown_count: int = Field(default=0, ge=0)
    security_clause_verdicts: list[JsonObject] = Field(default_factory=list)
    harness_policy_verdicts: list[JsonObject] = Field(default_factory=list)
    per_clause_records: list[JsonObject] = Field(default_factory=list)
    overall_compliance_status: OverallComplianceStatus = OverallComplianceStatus.UNKNOWN
    created_ts: str = ""


class OperationalEvidenceBinding(StrictBaseModel):
    run_id: str = Field(min_length=1)
    clause_id: str = Field(min_length=1)
    graph_snapshot_id: str | None = None
    resource_refs: list[str] = Field(default_factory=list)
    tool_calls: list[JsonObject] = Field(default_factory=list)
    gate_results: list[JsonObject] = Field(default_factory=list)
    stale_snapshot_flag: bool = False
    mixed_snapshot_flag: bool = False
    required_gate_events_present: bool = True
    harness_condition_id: str = ""


class ImplementationCheckReport(StrictBaseModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    harness_condition_id: str = ""
    doc_id: str = Field(min_length=1)
    spec_document_ref: str = ""
    intent_graph_ref: str = ""
    clause_verdict_matrix_ref: str = ""
    violated_clauses: list[str] = Field(default_factory=list)
    unknown_clauses: list[str] = Field(default_factory=list)
    satisfied_clauses: list[str] = Field(default_factory=list)
    security_clause_summary: JsonObject = Field(default_factory=dict)
    harness_policy_summary: JsonObject = Field(default_factory=dict)
    operational_compliance_verdict: OverallVerdict = OverallVerdict.UNKNOWN
    manifest_regression_verdict: VerdictValue = VerdictValue.UNKNOWN
    overall_verdict: OverallVerdict = OverallVerdict.UNKNOWN
    recommendation: RecommendationValue = RecommendationValue.UNKNOWN
    uncertainty: str = ""
    session_trace_manifest_ref: str = ""
    created_ts: str = ""
