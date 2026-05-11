"""Tests for the ExplanationRecord schema and ExplanationGenerator (Gap 7)."""

from __future__ import annotations


def test_explanation_record_schema() -> None:
    """ExplanationRecord defaults should match spec."""
    from llm_sca_tooling.qa.explainability import ExplanationRecord

    r = ExplanationRecord(explanation_id="exp:test", created_ts="2026-01-01T00:00:00Z")
    assert r.confidence == "unknown"
    assert r.reasoning_steps == []


def test_explanation_generator_creates_record() -> None:
    """ExplanationGenerator.generate should produce a populated record."""
    from llm_sca_tooling.qa.explainability import ExplanationGenerator

    gen = ExplanationGenerator()
    ev = [
        {
            "evidence_type": "file_node",
            "file_path": "src/main.py",
            "evidence_id": "ev:001",
        }
    ]
    rec = gen.generate("answer:001", ev)
    assert rec.answer_id == "answer:001"
    assert len(rec.reasoning_steps) == 1
    assert "src/main.py" in rec.reasoning_steps[0]
