"""SAST repair models."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from llm_sca_tooling.evaluation.models import now_ts


class StrictSASTModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AlertBinding(StrictSASTModel):
    alert_id: str
    sarif_alert_ref: str
    rule_id: str
    rule_family: str
    cwe_ids: list[str] = Field(default_factory=list)
    file_node_id: str | None = None
    file_path: str | None = None
    span: tuple[int, int] | None = None
    primary_symbol_node_ids: list[str] = Field(default_factory=list)
    related_symbol_node_ids: list[str] = Field(default_factory=list)
    dataflow_path_nodes: list[str] = Field(default_factory=list)
    cross_file_nodes: list[str] = Field(default_factory=list)
    graph_snapshot_id: str | None = None
    confidence: str
    diagnostics: list[str] = Field(default_factory=list)


class AlertClassification(StrictSASTModel):
    alert_id: str
    binding_ref: str
    classification: str
    tp_evidence: list[str] = Field(default_factory=list)
    fp_evidence: list[str] = Field(default_factory=list)
    confidence: str
    calibrated: bool = False
    suppression_history: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)


class PredicateMetadata(StrictSASTModel):
    rule_id: str
    rule_family: str
    predicate_text: str
    negated_predicate_text: str | None = None
    cwe_ids: list[str] = Field(default_factory=list)
    severity: str = "warning"
    description: str
    fix_guidance: str
    known_false_positive_patterns: list[str] = Field(default_factory=list)
    available_examples: int = 0
    source: str = "phase12-rule-db"
    confidence: str = "heuristic"


class PredicateExampleRecord(StrictSASTModel):
    rule_id: str
    negated_predicate: str | None
    corpus_id: str
    example_id: str
    file_path: str
    span: tuple[int, int] | None = None
    code_snippet: str
    snippet_language: str
    confidence: str
    retrieval_method: str
    repo_id: str | None = None


class CleanCorpusAdapter(Protocol):
    corpus_id: str
    corpus_version: str

    def supports_predicate_query(self) -> bool: ...
    def query_by_predicate(
        self, rule_id: str, negated_predicate: str | None
    ) -> list[PredicateExampleRecord]: ...
    def query_by_rule_family(
        self, rule_family: str
    ) -> list[PredicateExampleRecord]: ...
    def query_by_embedding(
        self, embedding: list[float], k: int
    ) -> list[PredicateExampleRecord]: ...


class RepairContext(StrictSASTModel):
    alert_id: str
    binding_ref: str
    classification_ref: str
    graph_slice_ref: str
    alert_explanation: str
    predicate_examples_ref: str
    interface_contracts_ref: str | None = None
    snapshot_id: str | None = None
    language: str
    file_path: str | None = None
    span: tuple[int, int] | None = None
    context_tokens_estimate: int
    budget_remaining: int
    provenance: dict[str, Any] = Field(default_factory=dict)


class SASTPatch(StrictSASTModel):
    alert_id: str
    diff_text: str
    diff_format: str = "unified"
    changed_files: list[str] = Field(default_factory=list)
    generator_model: str
    generation_method: str
    confidence: str
    certificate_text: str
    reasoning_chain: list[str] = Field(default_factory=list)
    dryrun_prediction_ref: str
    provenance: dict[str, Any] = Field(default_factory=dict)


class SuppressionProposal(StrictSASTModel):
    alert_id: str
    rule_id: str
    classification_ref: str
    suppression_kind: str
    annotation_text: str
    suppression_scope: str
    reviewer_required: bool = True
    offline_rule_evolution_candidate: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)


class SandboxResult(StrictSASTModel):
    alert_id: str
    sandbox_path: str
    patch_applied: bool
    apply_error: str | None = None
    sandbox_snapshot_id: str
    cleanup_policy: str = "delete-after-run"


class AnalyserRerunResult(StrictSASTModel):
    alert_id: str
    sandbox_snapshot_id: str
    analyser_id: str
    analyser_version: str
    rerun_status: str
    sarif_run_id_after: str
    rerun_diagnostic: str | None = None
    wall_ms: int = 0


class SARIFDeltaVerificationResult(StrictSASTModel):
    alert_id: str
    sarif_run_before_id: str
    sarif_run_after_id: str
    original_alert_gone: bool
    original_alert_remains: bool
    new_alerts: list[dict[str, Any]] = Field(default_factory=list)
    new_critical_or_error_alerts: list[dict[str, Any]] = Field(default_factory=list)
    severity_regressions: list[dict[str, Any]] = Field(default_factory=list)
    net_alert_delta: int = 0
    success: bool
    block_reason: str | None = None


class BuildTestResult(StrictSASTModel):
    alert_id: str
    sandbox_snapshot_id: str
    build_status: str
    test_run_status: str
    newly_failing_tests: list[str] = Field(default_factory=list)
    newly_passing_tests: list[str] = Field(default_factory=list)
    flaky_tests_detected: list[str] = Field(default_factory=list)
    reproduction_test_executed: bool = False
    reproduction_test_result: str = "not_available"
    wall_ms: int = 0
    diagnostics: list[str] = Field(default_factory=list)


class RemainingRiskNote(StrictSASTModel):
    alert_id: str
    risk_level: str
    risk_description: str
    verification_method_used: str
    unverified_paths: list[str] = Field(default_factory=list)
    recommended_followup: str


class SASTRepairReport(StrictSASTModel):
    report_id: str
    alert_id: str
    run_id: str
    harness_condition_id: str
    alert_binding_ref: str
    alert_classification_ref: str
    predicate_examples_ref: str
    repair_context_ref: str
    patch_ref: str | None = None
    suppression_proposal_ref: str | None = None
    sarif_delta_ref: str
    build_test_result_ref: str
    patch_risk_result_ref: str
    remaining_risk_note_ref: str
    success: bool
    verdict: str
    recommendation: str
    created_ts: str = Field(default_factory=now_ts)
