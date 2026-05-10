"""Tests for suppression-proposal generation."""

from __future__ import annotations

import pytest

from llm_sca_tooling.sast_repair.models import (
    AlertClassification,
    BindingConfidence,
    ClassificationConfidence,
    ClassificationValue,
    SuppressionKind,
)
from llm_sca_tooling.sast_repair.suppression import propose_suppression


def _cls(
    classification: ClassificationValue,
    confidence: ClassificationConfidence = ClassificationConfidence.ANALYSER,
) -> AlertClassification:
    return AlertClassification(
        alert_id="a1",
        binding_ref="b:a1",
        classification=classification,
        confidence=confidence,
    )


def test_propose_suppression_inline() -> None:
    proposal = propose_suppression(
        classification=_cls(ClassificationValue.LIKELY_FALSE_POSITIVE),
        rule_id="py.nullderef",
        file_path="src/x.py",
        binding_confidence=BindingConfidence.PARSER,
    )
    assert proposal is not None
    assert proposal.reviewer_required is True
    assert "noqa" in proposal.annotation_text


def test_propose_suppression_baseline_requires_sha() -> None:
    with pytest.raises(ValueError):
        propose_suppression(
            classification=_cls(ClassificationValue.LIKELY_FALSE_POSITIVE),
            rule_id="r",
            file_path=None,
            binding_confidence=BindingConfidence.PARSER,
            suppression_kind=SuppressionKind.BASELINE_ENTRY,
        )


def test_propose_suppression_baseline_with_sha() -> None:
    proposal = propose_suppression(
        classification=_cls(ClassificationValue.LIKELY_FALSE_POSITIVE),
        rule_id="r",
        file_path=None,
        binding_confidence=BindingConfidence.PARSER,
        suppression_kind=SuppressionKind.BASELINE_ENTRY,
        git_sha="deadbeef",
    )
    assert proposal is not None
    assert "deadbeef" in proposal.annotation_text


def test_propose_suppression_rule_evolution_candidate() -> None:
    proposal = propose_suppression(
        classification=_cls(ClassificationValue.LIKELY_FALSE_POSITIVE),
        rule_id="r",
        file_path=None,
        binding_confidence=BindingConfidence.PARSER,
        suppression_kind=SuppressionKind.RULE_EVOLUTION_CANDIDATE,
    )
    assert proposal is not None
    assert proposal.offline_rule_evolution_candidate is True


def test_propose_suppression_rejects_tp() -> None:
    proposal = propose_suppression(
        classification=_cls(ClassificationValue.LIKELY_TRUE_POSITIVE),
        rule_id="r",
        file_path=None,
        binding_confidence=BindingConfidence.PARSER,
    )
    assert proposal is None


def test_propose_suppression_rejects_low_confidence() -> None:
    proposal = propose_suppression(
        classification=_cls(
            ClassificationValue.LIKELY_FALSE_POSITIVE,
            ClassificationConfidence.HEURISTIC,
        ),
        rule_id="r",
        file_path=None,
        binding_confidence=BindingConfidence.HEURISTIC,
    )
    assert proposal is None
