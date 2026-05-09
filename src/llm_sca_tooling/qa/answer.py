"""Typed repository QA answer model."""

from __future__ import annotations

from pydantic import Field, model_validator

from llm_sca_tooling.qa.blame import BlameEntry
from llm_sca_tooling.qa.confidence import ConfidenceLabel
from llm_sca_tooling.qa.evidence_assembler import AnswerEvidence
from llm_sca_tooling.qa.graph_query import GraphPath
from llm_sca_tooling.qa.interface_lookup import InterfaceContractResult
from llm_sca_tooling.qa.question import QuestionClass
from llm_sca_tooling.schemas.base import SCHEMA_VERSION, StrictBaseModel


class RepoAnswer(StrictBaseModel):
    answer_id: str
    question_id: str
    question_class: QuestionClass
    answer_text: str
    confidence: ConfidenceLabel
    confidence_reason: str
    evidence: list[AnswerEvidence] = Field(default_factory=list)
    graph_node_ids: list[str] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    interface_contracts: list[InterfaceContractResult] = Field(default_factory=list)
    blame_entries: list[BlameEntry] | None = None
    uncertainty: str | None = None
    recommended_action: str | None = None
    synthesis_mode: str | None = None
    synthesis_model: str | None = None
    synthesis_tokens: int | None = None
    run_event_ids: list[str] = Field(default_factory=list)
    snapshot_ids: dict[str, str] = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_well_formed(self) -> RepoAnswer:
        if self.confidence != ConfidenceLabel.UNKNOWN and not self.evidence:
            raise ValueError("non-unknown answers require evidence")
        if (
            self.confidence in {ConfidenceLabel.PARSER, ConfidenceLabel.ANALYSER}
            and not self.graph_node_ids
        ):
            raise ValueError("parser/analyser answers require graph_node_ids")
        if (
            self.question_class == QuestionClass.BEHAVIOUR_TRACE
            and self.confidence == ConfidenceLabel.HEURISTIC
            and not self.uncertainty
        ):
            raise ValueError("heuristic behaviour-trace answers require uncertainty")
        if self.confidence == ConfidenceLabel.UNKNOWN and not self.recommended_action:
            raise ValueError("unknown answers require recommended_action")
        return self
