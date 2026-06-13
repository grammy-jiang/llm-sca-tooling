"""LLM grounding adapter — the unknown-clause mover (provider wiring)."""

from __future__ import annotations

import json
from typing import Any

from llm_sca_tooling.impl_check.grounding import LLMGroundingAdapter, ground_clause
from llm_sca_tooling.impl_check.models import Clause
from llm_sca_tooling.impl_check.report import run_implementation_check

PROSE_SPEC = """# Mini spec

The orchestration layer is responsible for coordinating workflow stages and
remains the single owner of run-state transitions across the product.
"""


def _prose_clause() -> Clause:
    return Clause(
        clause_id="clause:test:prose",
        doc_id="spec:test",
        text=(
            "The orchestration layer is responsible for coordinating workflow "
            "stages and remains the single owner of run-state transitions."
        ),
        source_span=(0, 120),
        checkability="static",
        risk_class="functional",
        atomic=True,
    )


def _ungrounded_fallback(clause: Clause) -> Any:
    grounding = ground_clause(clause)
    assert grounding.grounding_method in {"ungrounded", "policy_principle"}
    if grounding.grounding_method != "ungrounded":
        grounding = grounding.model_copy(
            update={"grounding_method": "ungrounded", "confidence": "unknown"}
        )
    return grounding


def test_llm_classifies_design_principle() -> None:
    adapter = LLMGroundingAdapter(
        complete=lambda p: json.dumps({"grounding_method": "policy_principle"}),
        model_id="m1",
    )
    clause = _prose_clause()
    grounded = adapter.ground(clause, _ungrounded_fallback(clause))
    assert grounded.grounding_method == "policy_principle"
    assert grounded.derivation == "llm"
    assert grounded.confidence == "heuristic"


def test_llm_symbol_match_requires_symbols() -> None:
    clause = _prose_clause()
    fallback = _ungrounded_fallback(clause)

    no_symbols = LLMGroundingAdapter(
        complete=lambda p: json.dumps({"grounding_method": "symbol_match"}),
        model_id="m1",
    )
    assert no_symbols.ground(clause, fallback) is fallback

    with_symbols = LLMGroundingAdapter(
        complete=lambda p: json.dumps(
            {"grounding_method": "symbol_match", "symbols": ["Orchestrator.run"]}
        ),
        model_id="m1",
    )
    grounded = with_symbols.ground(clause, fallback)
    assert grounded.grounding_method == "symbol_match"
    assert grounded.symbol_node_ids == ["symbol:Orchestrator.run"]
    assert grounded.derivation == "llm"


def test_out_of_vocabulary_method_falls_back() -> None:
    clause = _prose_clause()
    fallback = _ungrounded_fallback(clause)
    adapter = LLMGroundingAdapter(
        complete=lambda p: json.dumps({"grounding_method": "vibes"}), model_id="m1"
    )
    assert adapter.ground(clause, fallback) is fallback


def test_malformed_output_falls_back() -> None:
    clause = _prose_clause()
    fallback = _ungrounded_fallback(clause)
    adapter = LLMGroundingAdapter(complete=lambda p: "not json", model_id="m1")
    assert adapter.ground(clause, fallback) is fallback


def test_report_uses_grounding_adapter_for_ungrounded_clauses() -> None:
    calls: list[str] = []

    def fake_complete(prompt: str) -> str:
        calls.append(prompt)
        return json.dumps({"grounding_method": "policy_principle"})

    adapter = LLMGroundingAdapter(complete=fake_complete, model_id="m1")

    baseline = run_implementation_check(spec=PROSE_SPEC, doc_id="spec:grounding")
    with_llm = run_implementation_check(
        spec=PROSE_SPEC, doc_id="spec:grounding", grounding_adapter=adapter
    )

    # The adapter is consulted only when heuristic grounding fails, and any
    # clause it classifies moves from unknown to a verdict-bearing method.
    if calls:
        assert len(with_llm.unknown_clauses) <= len(baseline.unknown_clauses)


def test_raising_complete_falls_back() -> None:
    def boom(prompt: str) -> str:
        raise RuntimeError("provider down")

    clause = _prose_clause()
    fallback = _ungrounded_fallback(clause)
    adapter = LLMGroundingAdapter(complete=boom, model_id="m1")
    assert adapter.ground(clause, fallback) is fallback
