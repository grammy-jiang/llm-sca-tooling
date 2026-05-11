"""Typed answer model for repo-QA."""

from __future__ import annotations

import hashlib

from pydantic import Field, model_validator

from llm_sca_tooling.qa.evidence_assembler import AnswerEvidence
from llm_sca_tooling.qa.graph_query import GraphPath
from llm_sca_tooling.qa.interface_lookup import InterfaceContractResult
from llm_sca_tooling.qa.question import QuestionClass, StrictQaModel

__all__ = ["RepoAnswer", "make_answer_id", "recommended_action"]


class RepoAnswer(StrictQaModel):
    answer_id: str
    question_id: str
    question_class: QuestionClass
    answer_text: str
    confidence: str
    confidence_reason: str
    evidence: list[AnswerEvidence] = Field(default_factory=list)
    graph_node_ids: list[str] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    interface_contracts: list[InterfaceContractResult] = Field(default_factory=list)
    blame_entries: list[object] | None = None
    uncertainty: str | None = None
    recommended_action: str | None = None
    synthesis_mode: str | None = None
    synthesis_model: str | None = None
    synthesis_tokens: int | None = None
    run_event_ids: list[str] = Field(default_factory=list)
    snapshot_ids: dict[str, str] = Field(default_factory=dict)
    schema_version: str = "qa.answer.v1"

    @model_validator(mode="after")
    def _well_formed(self) -> RepoAnswer:
        if self.confidence != "unknown" and not self.evidence:
            raise ValueError("non-unknown answers require evidence")
        if self.confidence in {"parser", "analyser"} and not self.graph_node_ids:
            raise ValueError("parser/analyser answers require graph_node_ids")
        if self.confidence == "unknown" and not self.recommended_action:
            raise ValueError("unknown answers require recommended_action")
        if (
            self.question_class == QuestionClass.behaviour_trace
            and self.confidence == "heuristic"
            and not self.uncertainty
        ):
            raise ValueError("heuristic behaviour-trace answers require uncertainty")
        return self


def make_answer_id(question_id: str, evidence: list[AnswerEvidence]) -> str:
    material = question_id + "|" + "|".join(ev.evidence_id for ev in evidence)
    return f"a:{hashlib.sha256(material.encode()).hexdigest()[:16]}"


def recommended_action(question_class: QuestionClass) -> str:
    if question_class == QuestionClass.behaviour_trace:
        return "Check if the behaviour-trace ship-gate threshold has been met."
    if question_class == QuestionClass.symbol_loc:
        return "Register the repository containing the referenced symbol."
    if question_class == QuestionClass.contract_check:
        return "Run `plugin_reload` to refresh interface index after IDL changes."
    return "Run `graph_build` to index this repository."
