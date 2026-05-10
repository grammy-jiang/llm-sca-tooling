"""Fault-localisation contracts shared by Phase 9 components."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from llm_sca_tooling.indexing.summaries import SymbolSummaryRecord
from llm_sca_tooling.qa.blame import BlameEntry
from llm_sca_tooling.sarif.models import NormalizedAlert
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel
from llm_sca_tooling.schemas.graph import GraphNode
from llm_sca_tooling.schemas.provenance import ArtifactRef, SourceSpan
from llm_sca_tooling.storage.graph_queries import GraphSlice


class ConfidenceLevel(StrEnum):
    PARSER = "parser"
    ANALYSER = "analyser"
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"


class SignalType(StrEnum):
    KEYWORD = "keyword"
    EMBEDDING = "embedding"
    SARIF_PROXIMITY = "sarif_proximity"
    BLAME_HISTORY = "blame_history"
    GRAPH_NEIGHBOUR = "graph_neighbour"
    SBFL = "sbfl"
    MEMORY_HINT = "memory_hint"


class CandidateSignal(StrictBaseModel):
    signal_type: SignalType
    raw_score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(default=0.0, ge=0.0)
    weighted_score: float = Field(default=0.0, ge=0.0)
    evidence: str = Field(min_length=1)
    source_refs: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC

    def with_weight(self, weight: float) -> CandidateSignal:
        return self.model_copy(
            update={
                "weight": weight,
                "weighted_score": min(1.0, max(0.0, self.raw_score * weight)),
            }
        )


class CandidateFile(StrictBaseModel):
    candidate_id: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    repo_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    signals: list[CandidateSignal] = Field(default_factory=list)
    combined_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC
    evidence_summary: str | None = None
    snapshot_id: str = Field(default="", description="Snapshot identifier when known.")
    is_generated: bool = False

    @model_validator(mode="after")
    def validate_signal_presence(self) -> CandidateFile:
        if not self.signals and self.combined_score > 0.0:
            raise ValueError(
                "candidate with non-zero score requires at least one signal"
            )
        return self


class CandidateSymbol(StrictBaseModel):
    candidate_id: str = Field(min_length=1)
    symbol_node_id: str = Field(min_length=1)
    symbol_path: str = Field(min_length=1)
    symbol_type: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    repo_id: str = Field(min_length=1)
    span: SourceSpan | None = None
    signals: list[CandidateSignal] = Field(default_factory=list)
    combined_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC
    reasoning_chain: str | None = None
    uncertainty: str | None = None


class ContextBudget(StrictBaseModel):
    max_files: int = Field(default=8, ge=1, le=20)
    actual_files: int = Field(default=0, ge=0)
    max_graph_nodes: int = Field(default=2000, ge=1)
    actual_graph_nodes: int = Field(default=0, ge=0)
    max_symbol_summaries: int = Field(default=100, ge=0)
    actual_symbol_summaries: int = Field(default=0, ge=0)
    token_estimate: int | None = Field(default=None, ge=0)


class CodeSpan(StrictBaseModel):
    file_path: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    content: str
    node_id: str | None = None
    confidence: ConfidenceLevel
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_span_bounds(self) -> CodeSpan:
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        if self.end_line - self.start_line + 1 > 10:
            raise ValueError("exact source spans are capped at 10 lines")
        return self


class ContextFileEntry(StrictBaseModel):
    candidate_file: CandidateFile
    graph_slice: GraphSlice
    symbol_summaries: list[SymbolSummaryRecord] = Field(default_factory=list)
    sarif_alerts: list[NormalizedAlert] = Field(default_factory=list)
    build_test_evidence: list[GraphNode] = Field(default_factory=list)
    blame_entries: list[BlameEntry] = Field(default_factory=list)
    exact_spans: list[CodeSpan] = Field(default_factory=list)


class ContextBundle(StrictBaseModel):
    files: list[ContextFileEntry] = Field(default_factory=list)
    total_graph_nodes: int = Field(default=0, ge=0)
    total_graph_edges: int = Field(default=0, ge=0)
    total_symbol_summaries: int = Field(default=0, ge=0)
    total_sarif_alerts: int = Field(default=0, ge=0)
    budget_used: ContextBudget
    snapshot_ids: dict[str, str] = Field(default_factory=dict)
    is_over_budget: bool = False


class LocalisationResult(StrictBaseModel):
    ranked_files: list[CandidateFile] = Field(default_factory=list)
    ranked_symbols: list[CandidateSymbol] | None = None
    agreement_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    uncertainty: str | None = None
    diagnostics: list[JsonObject] = Field(default_factory=list)
    signals_used: list[SignalType] = Field(default_factory=list)
    signals_missing: list[SignalType] = Field(default_factory=list)
    context_bundle: ContextBundle | None = None
    context_bundle_ref: ArtifactRef | None = None
    run_event_ids: list[str] = Field(default_factory=list)
    snapshot_ids: dict[str, str] = Field(default_factory=dict)
    memory_hints_used: list[str] = Field(default_factory=list)
    memory_hints_rejected: list[str] = Field(default_factory=list)

    @field_validator("signals_used", "signals_missing")
    @classmethod
    def unique_signal_lists(cls, values: list[SignalType]) -> list[SignalType]:
        return list(dict.fromkeys(values))


class CandidateReasoningEntry(StrictBaseModel):
    candidate_id: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    reasoning_chain: str = Field(min_length=1)
    derivation: str = Field(pattern="^(deterministic|llm)$")
    evidence_citations: list[str] = Field(default_factory=list)


class RetrievalDiagnostic(StrictBaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: str = "warning"
    metadata: JsonObject = Field(default_factory=dict)
