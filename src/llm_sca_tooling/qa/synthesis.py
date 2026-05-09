"""Typed LLM synthesis boundary for repo QA."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import Field, field_validator

from llm_sca_tooling.qa.blame import BlameEntry
from llm_sca_tooling.qa.confidence import ConfidenceLabel
from llm_sca_tooling.qa.graph_query import GraphPath
from llm_sca_tooling.qa.interface_lookup import InterfaceContractResult
from llm_sca_tooling.qa.lookup import GraphNodeRef
from llm_sca_tooling.qa.question import QuestionClass
from llm_sca_tooling.schemas.base import StrictBaseModel


class SynthesisMode(StrEnum):
    NARRATIVE = "narrative"
    STRUCTURED = "structured"
    TECHNICAL_SUMMARY = "technical_summary"


class EvidenceSummary(StrictBaseModel):
    source_count: int
    highest_evidence_confidence: ConfidenceLabel
    has_graph_path: bool = False
    has_interface_contract: bool = False
    has_blame_chain: bool = False
    question_class_threshold_met: bool = False


class SynthesisInput(StrictBaseModel):
    question_class: QuestionClass
    normalized_question: str
    evidence_summary: EvidenceSummary
    graph_nodes: list[GraphNodeRef] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    interface_contracts: list[InterfaceContractResult] = Field(default_factory=list)
    blame_entries: list[BlameEntry] | None = None
    max_tokens: int = 512
    mode: SynthesisMode = SynthesisMode.TECHNICAL_SUMMARY


class SynthesisOutput(StrictBaseModel):
    answer_text: str
    cited_node_ids: list[str] = Field(default_factory=list)
    confidence_claim: str | None = None
    synthesis_model: str
    synthesis_tokens_used: int = 0
    derivation: str = "llm"

    @field_validator("cited_node_ids")
    @classmethod
    def validate_citations_are_distinct(cls, value: list[str]) -> list[str]:
        return sorted(set(value))


class SynthesisInterface(ABC):
    @abstractmethod
    def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisOutput:
        raise NotImplementedError


class NullSynthesisAdapter(SynthesisInterface):
    def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisOutput:
        if synthesis_input.graph_nodes:
            first = synthesis_input.graph_nodes[0]
            text = f"Found {len(synthesis_input.graph_nodes)} cited graph node(s); primary evidence is {first.symbol_path or first.file_path or first.node_id}."
        elif synthesis_input.graph_paths:
            text = f"Found {len(synthesis_input.graph_paths)} graph path(s) for the question."
        elif synthesis_input.interface_contracts:
            text = f"Found {len(synthesis_input.interface_contracts)} interface contract(s)."
        else:
            text = "No graph-backed evidence was found for this question."
        return SynthesisOutput(
            answer_text=text,
            cited_node_ids=[node.node_id for node in synthesis_input.graph_nodes],
            confidence_claim=None,
            synthesis_model="null",
            synthesis_tokens_used=0,
            derivation="deterministic",
        )


def override_confidence(
    _output: SynthesisOutput, evidence_confidence: ConfidenceLabel
) -> ConfidenceLabel:
    return evidence_confidence
