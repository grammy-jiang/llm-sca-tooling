"""Tests for sast_repair Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.sast_repair.models import (
    AlertBinding,
    AlertSpan,
    BindingConfidence,
    ClassificationConfidence,
    ClassificationValue,
    GenerationMethod,
    PredicateExampleRecord,
    PredicateMetadata,
    RemainingRiskNote,
    RetrievalMethod,
    RiskLevel,
    SASTPatch,
    SASTRepairReport,
    SuppressionKind,
    SuppressionProposal,
    Verdict,
)


def test_alert_span_validates_positive() -> None:
    span = AlertSpan(file_path="a.py", start_line=1)
    assert span.start_line == 1
    with pytest.raises(ValidationError):
        AlertSpan(file_path="a.py", start_line=0)


def test_alert_binding_defaults_and_extra_forbid() -> None:
    binding = AlertBinding(alert_id="a1", sarif_alert_ref="sa1", rule_id="py.nullderef")
    assert binding.confidence is BindingConfidence.HEURISTIC
    with pytest.raises(ValidationError):
        AlertBinding(
            alert_id="a1",
            sarif_alert_ref="sa1",
            rule_id="r",
            unexpected_field=True,  # type: ignore[call-arg]
        )


def test_predicate_example_record_required_fields() -> None:
    rec = PredicateExampleRecord(
        rule_id="r",
        corpus_id="c",
        example_id="e",
        file_path="p.py",
        code_snippet="snippet",
    )
    assert rec.retrieval_method is RetrievalMethod.PREDICATE_NEGATION


def test_sast_patch_default_null() -> None:
    patch = SASTPatch(alert_id="a1")
    assert patch.generation_method is GenerationMethod.NULL_REPAIR


def test_suppression_proposal_requires_annotation() -> None:
    sp = SuppressionProposal(
        alert_id="a1",
        rule_id="r",
        classification_ref="c:1",
        suppression_kind=SuppressionKind.INLINE_COMMENT,
        annotation_text="# noqa",
    )
    assert sp.reviewer_required is True


def test_remaining_risk_note_levels() -> None:
    note = RemainingRiskNote(
        alert_id="a1", risk_level=RiskLevel.HIGH, risk_description="x"
    )
    assert note.risk_level is RiskLevel.HIGH


def test_predicate_metadata_default_unknown() -> None:
    meta = PredicateMetadata(rule_id="r")
    assert meta.source == "unknown"
    assert meta.confidence is ClassificationConfidence.UNKNOWN


def test_sast_repair_report_minimal_construction() -> None:
    binding = AlertBinding(alert_id="a", sarif_alert_ref="s", rule_id="r")
    classification = type(binding).__module__  # placeholder use
    from llm_sca_tooling.sast_repair.models import AlertClassification

    cls = AlertClassification(
        alert_id="a",
        binding_ref="b:a",
        classification=ClassificationValue.UNKNOWN,
    )
    meta = PredicateMetadata(rule_id="r")
    report = SASTRepairReport(
        report_id="rep:1",
        alert_id="a",
        alert_binding=binding,
        alert_classification=cls,
        predicate_metadata=meta,
    )
    assert report.verdict is Verdict.UNKNOWN
    assert report.success is False
    assert classification  # silence unused
