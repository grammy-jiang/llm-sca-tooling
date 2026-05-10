"""Pydantic v2 models for Phase 12 SAST repair."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from llm_sca_tooling.evaluation.models import utc_now_ts
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, id_field


class BindingConfidence(StrEnum):
    PARSER = "parser"
    ANALYSER = "analyser"
    HEURISTIC = "heuristic"
    NONE = "none"


class ClassificationValue(StrEnum):
    LIKELY_TRUE_POSITIVE = "likely_true_positive"
    LIKELY_FALSE_POSITIVE = "likely_false_positive"
    UNKNOWN = "unknown"


class ClassificationConfidence(StrEnum):
    PARSER = "parser"
    ANALYSER = "analyser"
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"


class RetrievalMethod(StrEnum):
    PREDICATE_NEGATION = "predicate_negation"
    RULE_FAMILY_MATCH = "rule_family_match"
    EMBEDDING_SIMILARITY = "embedding_similarity"


class GenerationMethod(StrEnum):
    PREDICATE_REPAIR = "predicate_repair"
    GRAPH_SLICE_REPAIR = "graph_slice_repair"
    NULL_REPAIR = "null_repair"


class SuppressionKind(StrEnum):
    INLINE_COMMENT = "inline_comment"
    BASELINE_ENTRY = "baseline_entry"
    RULE_EVOLUTION_CANDIDATE = "rule_evolution_candidate"


class RerunStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class RiskLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Verdict(StrEnum):
    ALERT_FIXED = "alert_fixed"
    ALERT_FIXED_WITH_RISK = "alert_fixed_with_risk"
    PARTIALLY_FIXED = "partially_fixed"
    REPAIR_FAILED = "repair_failed"
    REPAIR_BLOCKED = "repair_blocked"
    FALSE_POSITIVE_SUPPRESSED = "false_positive_suppressed"
    UNKNOWN = "unknown"


class AlertSpan(StrictBaseModel):
    file_path: str = Field(min_length=1)
    start_line: int | None = Field(default=None, ge=1)
    start_column: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    end_column: int | None = Field(default=None, ge=1)


class AlertBinding(StrictBaseModel):
    alert_id: str = id_field("Alert identifier from SARIF normalisation.")
    sarif_alert_ref: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    rule_family: str = "other"
    cwe_ids: list[str] = Field(default_factory=list)
    file_node_id: str | None = None
    file_path: str | None = None
    span: AlertSpan | None = None
    primary_symbol_node_ids: list[str] = Field(default_factory=list)
    related_symbol_node_ids: list[str] = Field(default_factory=list)
    dataflow_path_nodes: list[str] = Field(default_factory=list)
    cross_file_nodes: list[str] = Field(default_factory=list)
    graph_snapshot_id: str | None = None
    confidence: BindingConfidence = BindingConfidence.HEURISTIC
    diagnostics: list[JsonObject] = Field(default_factory=list)


class AlertClassification(StrictBaseModel):
    alert_id: str = Field(min_length=1)
    binding_ref: str = Field(min_length=1)
    classification: ClassificationValue
    tp_evidence: list[str] = Field(default_factory=list)
    fp_evidence: list[str] = Field(default_factory=list)
    confidence: ClassificationConfidence = ClassificationConfidence.UNKNOWN
    calibrated: bool = False
    suppression_history: list[JsonObject] = Field(default_factory=list)
    diagnostics: list[JsonObject] = Field(default_factory=list)


class PredicateMetadata(StrictBaseModel):
    rule_id: str = Field(min_length=1)
    rule_family: str = "other"
    predicate_text: str | None = None
    negated_predicate_text: str | None = None
    cwe_ids: list[str] = Field(default_factory=list)
    severity: str | None = None
    description: str | None = None
    fix_guidance: str | None = None
    known_false_positive_patterns: list[str] = Field(default_factory=list)
    available_examples: int = 0
    source: str = "unknown"
    confidence: ClassificationConfidence = ClassificationConfidence.UNKNOWN


class PredicateExampleRecord(StrictBaseModel):
    rule_id: str = Field(min_length=1)
    negated_predicate: str | None = None
    corpus_id: str = Field(min_length=1)
    example_id: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    span: AlertSpan | None = None
    code_snippet: str = Field(min_length=1)
    snippet_language: str = "text"
    confidence: ClassificationConfidence = ClassificationConfidence.HEURISTIC
    retrieval_method: RetrievalMethod = RetrievalMethod.PREDICATE_NEGATION


class RepairContext(StrictBaseModel):
    alert_id: str = Field(min_length=1)
    binding_ref: str = Field(min_length=1)
    classification_ref: str = Field(min_length=1)
    graph_slice_ref: str | None = None
    alert_explanation: str = Field(min_length=1)
    predicate_examples_ref: list[str] = Field(default_factory=list)
    interface_contracts_ref: list[str] = Field(default_factory=list)
    snapshot_id: str | None = None
    language: str | None = None
    file_path: str | None = None
    span: AlertSpan | None = None
    context_tokens_estimate: int = Field(ge=0, default=0)
    budget_remaining: int = Field(ge=0, default=0)
    provenance: JsonObject = Field(default_factory=dict)


class SASTPatch(StrictBaseModel):
    alert_id: str = Field(min_length=1)
    diff_text: str = ""
    diff_format: str = "unified"
    changed_files: list[str] = Field(default_factory=list)
    generator_model: str = "null-adapter"
    generation_method: GenerationMethod = GenerationMethod.NULL_REPAIR
    confidence: ClassificationConfidence = ClassificationConfidence.UNKNOWN
    certificate_text: str | None = None
    reasoning_chain: list[str] = Field(default_factory=list)
    dryrun_prediction_ref: str | None = None
    provenance: JsonObject = Field(default_factory=dict)


class SuppressionProposal(StrictBaseModel):
    alert_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    classification_ref: str = Field(min_length=1)
    suppression_kind: SuppressionKind
    annotation_text: str = Field(min_length=1)
    suppression_scope: str = "alert"
    reviewer_required: bool = True
    offline_rule_evolution_candidate: bool = False
    provenance: JsonObject = Field(default_factory=dict)


class SandboxResult(StrictBaseModel):
    alert_id: str = Field(min_length=1)
    sandbox_path: str
    patch_applied: bool
    apply_error: str | None = None
    sandbox_snapshot_id: str | None = None
    cleanup_policy: str = "always"


class AnalyserRerunResult(StrictBaseModel):
    alert_id: str = Field(min_length=1)
    sandbox_snapshot_id: str | None = None
    analyser_id: str
    analyser_version: str | None = None
    rerun_status: RerunStatus
    sarif_run_id_after: str | None = None
    rerun_diagnostic: str | None = None
    wall_ms: int = Field(ge=0, default=0)


class SARIFDeltaVerificationResult(StrictBaseModel):
    alert_id: str = Field(min_length=1)
    sarif_run_before_id: str | None = None
    sarif_run_after_id: str | None = None
    original_alert_gone: bool
    original_alert_remains: bool
    new_alerts: list[JsonObject] = Field(default_factory=list)
    new_critical_or_error_alerts: list[JsonObject] = Field(default_factory=list)
    severity_regressions: list[JsonObject] = Field(default_factory=list)
    net_alert_delta: int = 0
    success: bool = False
    block_reason: str | None = None


class BuildTestResult(StrictBaseModel):
    alert_id: str = Field(min_length=1)
    sandbox_snapshot_id: str | None = None
    build_status: str
    test_run_status: str
    newly_failing_tests: list[str] = Field(default_factory=list)
    newly_passing_tests: list[str] = Field(default_factory=list)
    flaky_tests_detected: list[str] = Field(default_factory=list)
    reproduction_test_executed: bool = False
    reproduction_test_result: str | None = None
    wall_ms: int = Field(ge=0, default=0)
    diagnostics: list[JsonObject] = Field(default_factory=list)


class RemainingRiskNote(StrictBaseModel):
    alert_id: str = Field(min_length=1)
    risk_level: RiskLevel
    risk_description: str = Field(min_length=1)
    verification_method_used: list[str] = Field(default_factory=list)
    unverified_paths: list[str] = Field(default_factory=list)
    recommended_followup: list[str] = Field(default_factory=list)


class SASTRepairReport(StrictBaseModel):
    report_id: str = id_field("SAST repair report identifier.")
    alert_id: str = Field(min_length=1)
    run_id: str | None = None
    harness_condition_id: str | None = None
    alert_binding: AlertBinding
    alert_classification: AlertClassification
    predicate_metadata: PredicateMetadata
    predicate_examples: list[PredicateExampleRecord] = Field(default_factory=list)
    repair_context: RepairContext | None = None
    patch: SASTPatch | None = None
    suppression_proposal: SuppressionProposal | None = None
    sandbox_result: SandboxResult | None = None
    analyser_rerun: AnalyserRerunResult | None = None
    sarif_delta: SARIFDeltaVerificationResult | None = None
    build_test_result: BuildTestResult | None = None
    patch_risk_result: JsonObject | None = None
    remaining_risk_notes: list[RemainingRiskNote] = Field(default_factory=list)
    success: bool = False
    verdict: Verdict = Verdict.UNKNOWN
    recommendation: str = "review-required"
    diagnostics: list[JsonObject] = Field(default_factory=list)
    created_ts: str = Field(default_factory=utc_now_ts)
