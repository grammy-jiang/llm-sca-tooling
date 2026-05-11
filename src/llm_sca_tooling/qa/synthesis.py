"""Typed synthesis boundary for repo-QA."""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from pydantic import Field, model_validator

from llm_sca_tooling.qa.evidence_assembler import AnswerEvidence
from llm_sca_tooling.qa.graph_query import GraphPath
from llm_sca_tooling.qa.interface_lookup import InterfaceContractResult
from llm_sca_tooling.qa.lookup import GraphNodeRef
from llm_sca_tooling.qa.question import QuestionClass, StrictQaModel

__all__ = [
    "EvidenceSummary",
    "NullSynthesisAdapter",
    "SynthesisInput",
    "SynthesisInterface",
    "SynthesisMode",
    "SynthesisOutput",
]


class SynthesisMode(str, Enum):
    narrative = "narrative"
    structured = "structured"
    technical_summary = "technical_summary"


class EvidenceSummary(StrictQaModel):
    source_count: int
    highest_evidence_confidence: str
    has_graph_path: bool
    has_interface_contract: bool
    has_blame_chain: bool
    question_class_threshold_met: bool


class SynthesisInput(StrictQaModel):
    question_class: QuestionClass
    normalized_question: str
    evidence_summary: EvidenceSummary
    graph_nodes: list[GraphNodeRef] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    interface_contracts: list[InterfaceContractResult] = Field(default_factory=list)
    blame_entries: list[object] | None = None
    max_tokens: int = 512
    mode: SynthesisMode = SynthesisMode.technical_summary


class SynthesisOutput(StrictQaModel):
    answer_text: str
    cited_node_ids: list[str] = Field(default_factory=list)
    confidence_claim: str | None = None
    synthesis_model: str
    synthesis_tokens_used: int
    derivation: str = "llm"

    @model_validator(mode="after")
    def _token_count_is_non_negative(self) -> SynthesisOutput:
        if self.synthesis_tokens_used < 0:
            raise ValueError("synthesis_tokens_used must be non-negative")
        return self


class SynthesisInterface(Protocol):
    def synthesize(self, payload: SynthesisInput) -> SynthesisOutput: ...


class NullSynthesisAdapter:
    def synthesize(self, payload: SynthesisInput) -> SynthesisOutput:
        cited = [node.node_id for node in payload.graph_nodes]
        text = (
            f"{payload.question_class.value} answer assembled from "
            f"{payload.evidence_summary.source_count} evidence item(s)."
        )
        return SynthesisOutput(
            answer_text=text,
            cited_node_ids=cited,
            synthesis_model="null",
            synthesis_tokens_used=0,
            derivation="deterministic",
        )


def evidence_summary(evidence: list[AnswerEvidence]) -> EvidenceSummary:
    order = {"unknown": 0, "heuristic": 1, "analyser": 2, "parser": 3}
    highest = max(
        (ev.confidence for ev in evidence),
        key=lambda c: order.get(c, 0),
        default="unknown",
    )
    types = {ev.evidence_type.value for ev in evidence}
    return EvidenceSummary(
        source_count=len(evidence),
        highest_evidence_confidence=highest,
        has_graph_path="GRAPH_PATH" in types,
        has_interface_contract="INTERFACE_CONTRACT" in types,
        has_blame_chain="BLAME_ENTRY" in types,
        question_class_threshold_met=bool(evidence),
    )
