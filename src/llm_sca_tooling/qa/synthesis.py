"""Typed synthesis boundary for repo-QA."""

from __future__ import annotations

import json
from collections.abc import Callable
from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import Field, model_validator

from llm_sca_tooling.qa.evidence_assembler import AnswerEvidence
from llm_sca_tooling.qa.graph_query import GraphPath
from llm_sca_tooling.qa.interface_lookup import InterfaceContractResult
from llm_sca_tooling.qa.lookup import GraphNodeRef
from llm_sca_tooling.qa.question import QuestionClass, StrictQaModel

__all__ = [
    "EvidenceSummary",
    "LLMSynthesisAdapter",
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


@runtime_checkable
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


_PROMPT_TEMPLATE = """\
You are answering a repository question from typed evidence. Use only the
evidence below; do not invent files, symbols, or behaviour. Answers must be
short, factual, and cite the node ids they rely on.

question_class: {question_class}
question: {question}
mode: {mode}
evidence: {source_count} item(s), highest confidence {highest_confidence}
graph_nodes:
{nodes}

Respond with a single JSON object and nothing else:
{{"answer_text": "<answer grounded in the evidence>",
 "cited_node_ids": ["<node ids from graph_nodes that support the answer>"]}}
"""


class LLMSynthesisAdapter:
    """Synthesis adapter backed by an injected LLM completion callable.

    Fail-closed: unparseable or empty LLM output falls back to the
    deterministic null adapter, and citations are filtered to the evidence
    nodes that were actually provided — the LLM cannot introduce sources.
    """

    version = "b2.v1"

    def __init__(
        self,
        *,
        complete: Callable[[str], str],
        model_id: str,
    ) -> None:
        self._complete = complete
        self.model_id = model_id

    def synthesize(self, payload: SynthesisInput) -> SynthesisOutput:
        node_lines = "\n".join(
            f"- {node.node_id} ({node.node_type}, {node.file_path or 'no file'})"
            for node in payload.graph_nodes[:20]
        )
        prompt = _PROMPT_TEMPLATE.format(
            question_class=payload.question_class.value,
            question=payload.normalized_question,
            mode=payload.mode.value,
            source_count=payload.evidence_summary.source_count,
            highest_confidence=payload.evidence_summary.highest_evidence_confidence,
            nodes=node_lines or "- none",
        )
        raw = self._complete(prompt)
        parsed = self._parse_response(raw)
        answer_text = parsed.get("answer_text")
        if not isinstance(answer_text, str) or not answer_text.strip():
            return NullSynthesisAdapter().synthesize(payload)

        allowed = {node.node_id for node in payload.graph_nodes}
        raw_cited = parsed.get("cited_node_ids")
        cited_candidates = raw_cited if isinstance(raw_cited, list) else []
        cited = [
            node_id
            for node_id in cited_candidates
            if isinstance(node_id, str) and node_id in allowed
        ]
        return SynthesisOutput(
            answer_text=answer_text.strip(),
            cited_node_ids=cited,
            synthesis_model=self.model_id,
            synthesis_tokens_used=max(1, (len(prompt) + len(raw)) // 4),
            derivation="llm",
        )

    @staticmethod
    def _parse_response(raw: str) -> dict[str, object]:
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed


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
