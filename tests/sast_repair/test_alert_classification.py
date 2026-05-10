"""Tests for alert classification."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.alert_classification import classify_alert
from llm_sca_tooling.sast_repair.models import (
    AlertBinding,
    BindingConfidence,
    ClassificationConfidence,
    ClassificationValue,
)


def _binding(confidence: BindingConfidence = BindingConfidence.PARSER) -> AlertBinding:
    return AlertBinding(
        alert_id="a1",
        sarif_alert_ref="sa1",
        rule_id="py.nullderef",
        confidence=confidence,
    )


def test_classify_likely_true_positive_parser() -> None:
    cls = classify_alert(
        binding=_binding(),
        has_dataflow_edges=True,
        security_sensitive_symbol=True,
    )
    assert cls.classification is ClassificationValue.LIKELY_TRUE_POSITIVE
    assert cls.confidence is ClassificationConfidence.PARSER


def test_classify_likely_false_positive_parser() -> None:
    cls = classify_alert(
        binding=_binding(),
        has_dataflow_edges=False,
        test_only_symbol=True,
        high_fp_rule=True,
    )
    assert cls.classification is ClassificationValue.LIKELY_FALSE_POSITIVE
    assert cls.confidence is ClassificationConfidence.PARSER


def test_classify_unknown_when_no_evidence() -> None:
    cls = classify_alert(
        binding=_binding(BindingConfidence.NONE),
        suppression_comment_present=True,
    )
    assert cls.classification is ClassificationValue.UNKNOWN
    assert any(d["code"] == "insufficient_evidence" for d in cls.diagnostics)


def test_classify_analyser_confidence_for_tp() -> None:
    cls = classify_alert(
        binding=_binding(BindingConfidence.ANALYSER),
        security_sensitive_symbol=True,
    )
    assert cls.confidence is ClassificationConfidence.ANALYSER


def test_classify_analyser_confidence_for_fp() -> None:
    cls = classify_alert(
        binding=_binding(BindingConfidence.ANALYSER),
        high_fp_rule=True,
        test_only_symbol=True,
        historical_suppressions=[{"reason": "intentional"}],
    )
    assert cls.classification is ClassificationValue.LIKELY_FALSE_POSITIVE
    assert cls.confidence is ClassificationConfidence.ANALYSER


def test_classify_heuristic_confidence_fp() -> None:
    cls = classify_alert(
        binding=_binding(BindingConfidence.HEURISTIC),
        high_fp_rule=True,
        test_only_symbol=True,
    )
    assert cls.confidence is ClassificationConfidence.HEURISTIC
