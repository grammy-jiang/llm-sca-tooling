"""Tests for repair-context construction."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.alert_classification import classify_alert
from llm_sca_tooling.sast_repair.models import (
    AlertBinding,
    BindingConfidence,
    PredicateExampleRecord,
    RetrievalMethod,
)
from llm_sca_tooling.sast_repair.predicate_metadata import extract_predicate_metadata
from llm_sca_tooling.sast_repair.repair_context import build_repair_context


def _binding() -> AlertBinding:
    return AlertBinding(
        alert_id="a1",
        sarif_alert_ref="sa1",
        rule_id="py.nullderef",
        rule_family="null-dereference",
        confidence=BindingConfidence.PARSER,
        file_path="src/example.py",
    )


def _example(idx: int = 1) -> PredicateExampleRecord:
    return PredicateExampleRecord(
        rule_id="py.nullderef",
        corpus_id="c",
        example_id=f"e{idx}",
        file_path="x.py",
        code_snippet="snippet" * 10,
        retrieval_method=RetrievalMethod.PREDICATE_NEGATION,
    )


def test_build_repair_context_with_examples() -> None:
    binding = _binding()
    classification = classify_alert(binding=binding, has_dataflow_edges=True)
    metadata = extract_predicate_metadata(rule_id="py.nullderef")
    ctx = build_repair_context(
        binding=binding,
        classification=classification,
        metadata=metadata,
        examples=[_example(1), _example(2)],
    )
    assert ctx.alert_id == "a1"
    assert "py.nullderef" in ctx.alert_explanation
    assert len(ctx.predicate_examples_ref) == 2
    assert ctx.budget_remaining >= 0


def test_build_repair_context_budget_exhausted() -> None:
    binding = _binding()
    classification = classify_alert(binding=binding, has_dataflow_edges=True)
    metadata = extract_predicate_metadata(rule_id="py.nullderef")
    big = PredicateExampleRecord(
        rule_id="py.nullderef",
        corpus_id="c",
        example_id="big",
        file_path="x.py",
        code_snippet="x" * 4000,
    )
    ctx = build_repair_context(
        binding=binding,
        classification=classification,
        metadata=metadata,
        examples=[big],
        budget=50,
    )
    assert ctx.predicate_examples_ref == []


def test_build_repair_context_no_examples() -> None:
    binding = _binding()
    classification = classify_alert(binding=binding, has_dataflow_edges=True)
    metadata = extract_predicate_metadata(rule_id="py.nullderef")
    ctx = build_repair_context(
        binding=binding,
        classification=classification,
        metadata=metadata,
        examples=[],
    )
    assert "no predicate examples" in ctx.alert_explanation
