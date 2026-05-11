"""Fault-localisation models shared across Phase 9 modules."""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "CandidateFile",
    "CandidateSignal",
    "CandidateSymbol",
    "CodeSpan",
    "ConfidenceLevel",
    "ContextBudget",
    "ContextBundle",
    "ContextFileEntry",
    "LocalisationResult",
    "SignalType",
    "candidate_id",
]


class StrictFlModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfidenceLevel(str, Enum):
    unknown = "unknown"
    heuristic = "heuristic"
    analyser = "analyser"
    parser = "parser"


class SignalType(str, Enum):
    keyword = "KEYWORD"
    embedding = "EMBEDDING"
    sarif_proximity = "SARIF_PROXIMITY"
    blame_history = "BLAME_HISTORY"
    graph_neighbour = "GRAPH_NEIGHBOUR"
    sbfl = "SBFL"
    memory_hint = "MEMORY_HINT"


class CandidateSignal(StrictFlModel):
    signal_type: SignalType
    raw_score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0)
    weighted_score: float = Field(ge=0.0)
    evidence: str
    source_refs: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.heuristic


class CandidateFile(StrictFlModel):
    candidate_id: str
    file_path: str
    repo_id: str
    node_id: str
    signals: list[CandidateSignal] = Field(default_factory=list)
    combined_score: float = Field(ge=0.0, le=1.0)
    confidence: ConfidenceLevel = ConfidenceLevel.heuristic
    evidence_summary: str | None = None
    snapshot_id: str
    is_generated: bool = False


class CandidateSymbol(StrictFlModel):
    candidate_id: str
    symbol_node_id: str
    symbol_path: str
    symbol_type: str
    file_path: str
    repo_id: str
    span: dict[str, Any] | None = None
    signals: list[CandidateSignal] = Field(default_factory=list)
    combined_score: float = Field(ge=0.0, le=1.0)
    confidence: ConfidenceLevel = ConfidenceLevel.heuristic
    reasoning_chain: str | None = None
    uncertainty: str | None = None


class CodeSpan(StrictFlModel):
    file_path: str
    start_line: int
    end_line: int
    content: str
    node_id: str | None = None
    confidence: ConfidenceLevel
    reason: str

    @model_validator(mode="after")
    def _bounded(self) -> CodeSpan:
        if len(self.content.splitlines()) > 10:
            raise ValueError("CodeSpan content must not exceed ten lines")
        return self


class ContextBudget(StrictFlModel):
    max_files: int = 8
    actual_files: int = 0
    max_graph_nodes: int = 200
    actual_graph_nodes: int = 0
    max_symbol_summaries: int = 50
    actual_symbol_summaries: int = 0
    token_estimate: int | None = None


class ContextFileEntry(StrictFlModel):
    candidate_file: CandidateFile
    graph_slice: dict[str, Any] = Field(default_factory=dict)
    symbol_summaries: list[dict[str, Any]] = Field(default_factory=list)
    sarif_alerts: list[dict[str, Any]] = Field(default_factory=list)
    build_test_evidence: list[dict[str, Any]] = Field(default_factory=list)
    blame_entries: list[dict[str, Any]] = Field(default_factory=list)
    exact_spans: list[CodeSpan] = Field(default_factory=list)


class ContextBundle(StrictFlModel):
    files: list[ContextFileEntry]
    total_graph_nodes: int
    total_graph_edges: int
    total_symbol_summaries: int
    total_sarif_alerts: int
    budget_used: ContextBudget
    snapshot_ids: dict[str, str] = Field(default_factory=dict)
    is_over_budget: bool = False


class LocalisationResult(StrictFlModel):
    ranked_files: list[CandidateFile]
    ranked_symbols: list[CandidateSymbol] | None = None
    agreement_score: float = Field(ge=0.0, le=1.0)
    confidence: ConfidenceLevel
    uncertainty: str | None = None
    signals_used: list[str] = Field(default_factory=list)
    signals_missing: list[str] = Field(default_factory=list)
    context_bundle_ref: dict[str, Any] | None = None
    run_event_ids: list[str] = Field(default_factory=list)
    snapshot_ids: dict[str, str] = Field(default_factory=dict)


def candidate_id(repo_id: str, file_path: str, suffix: str = "file") -> str:
    digest = hashlib.sha256(f"{repo_id}:{file_path}:{suffix}".encode()).hexdigest()
    return f"fl:{suffix}:{digest[:16]}"
