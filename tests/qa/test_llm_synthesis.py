"""LLM synthesis adapter for repo-QA (Tier B2)."""

from __future__ import annotations

import json

from llm_sca_tooling.qa.lookup import GraphNodeRef
from llm_sca_tooling.qa.question import QuestionClass
from llm_sca_tooling.qa.synthesis import (
    EvidenceSummary,
    LLMSynthesisAdapter,
    NullSynthesisAdapter,
    SynthesisInput,
    SynthesisInterface,
    SynthesisMode,
)


def _payload() -> SynthesisInput:
    return SynthesisInput(
        question_class=QuestionClass.symbol_loc,
        normalized_question="where is validate defined",
        evidence_summary=EvidenceSummary(
            source_count=2,
            highest_evidence_confidence="parser",
            has_graph_path=True,
            has_interface_contract=False,
            has_blame_chain=False,
            question_class_threshold_met=True,
        ),
        graph_nodes=[
            GraphNodeRef(
                node_id="node:function:validate",
                node_type="function",
                repo_id="repo:test",
                file_path="src/user_service.py",
                source="lookup",
            ),
            GraphNodeRef(
                node_id="node:file:user_service",
                node_type="file",
                repo_id="repo:test",
                file_path="src/user_service.py",
                source="lookup",
            ),
        ],
        mode=SynthesisMode.technical_summary,
    )


def test_llm_adapter_satisfies_interface() -> None:
    adapter = LLMSynthesisAdapter(complete=lambda p: "{}", model_id="m1")
    assert isinstance(adapter, SynthesisInterface)


def test_llm_synthesis_produces_cited_answer() -> None:
    def fake_complete(prompt: str) -> str:
        assert "where is validate defined" in prompt
        assert "node:function:validate" in prompt
        return json.dumps(
            {
                "answer_text": "validate is defined in src/user_service.py.",
                "cited_node_ids": ["node:function:validate"],
            }
        )

    adapter = LLMSynthesisAdapter(complete=fake_complete, model_id="m1")
    output = adapter.synthesize(_payload())

    assert "src/user_service.py" in output.answer_text
    assert output.cited_node_ids == ["node:function:validate"]
    assert output.synthesis_model == "m1"
    assert output.derivation == "llm"
    assert output.synthesis_tokens_used > 0


def test_invented_citations_are_dropped() -> None:
    adapter = LLMSynthesisAdapter(
        complete=lambda p: json.dumps(
            {
                "answer_text": "answer",
                "cited_node_ids": ["node:function:validate", "node:made:up"],
            }
        ),
        model_id="m1",
    )
    output = adapter.synthesize(_payload())
    # Citations must be a subset of the provided evidence nodes.
    assert output.cited_node_ids == ["node:function:validate"]


def test_malformed_llm_output_falls_back_to_null() -> None:
    adapter = LLMSynthesisAdapter(complete=lambda p: "not json", model_id="m1")
    output = adapter.synthesize(_payload())

    null_output = NullSynthesisAdapter().synthesize(_payload())
    assert output.answer_text == null_output.answer_text
    assert output.derivation == "deterministic"
    assert output.synthesis_model == "null"


def test_empty_answer_text_falls_back_to_null() -> None:
    adapter = LLMSynthesisAdapter(
        complete=lambda p: json.dumps({"answer_text": "  "}), model_id="m1"
    )
    output = adapter.synthesize(_payload())
    assert output.derivation == "deterministic"
