"""Tests for verdict and evidence models."""

from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.evidence import (
    EvidenceBundle,
    EvidenceItem,
    EvidenceSupport,
    SnapshotConsistency,
)
from llm_sca_tooling.schemas.provenance import EvidenceStrength, PolicyAction
from llm_sca_tooling.schemas.verdicts import (
    ReasoningStep,
    Verdict,
    VerdictValue,
)

NOW = "2026-05-09T12:00:00Z"


def _make_verdict(
    value: VerdictValue,
    steps: list[ReasoningStep],
    parser_provenance,
) -> Verdict:
    return Verdict(
        verdict_id="v:1",
        workflow="test",
        subject_ref="node:1",
        verdict=value,
        confidence=0.9,
        evidence_bundle_id="bun:1",
        reasoning_chain=steps,
        recommended_action="review",
        policy_action=PolicyAction.allow,
        provenance=parser_provenance,
    )


def _hard_step() -> ReasoningStep:
    return ReasoningStep(
        step_id="s1",
        claim="tests pass",
        strength=EvidenceStrength.hard_static,
    )


def _soft_step() -> ReasoningStep:
    return ReasoningStep(
        step_id="s2",
        claim="looks good",
        strength=EvidenceStrength.soft_llm,
    )


def test_positive_verdict_with_hard_evidence(parser_provenance) -> None:
    v = _make_verdict(VerdictValue.satisfied, [_hard_step()], parser_provenance)
    assert v.verdict == VerdictValue.satisfied


def test_positive_verdict_with_only_soft_llm_rejected(parser_provenance) -> None:
    with pytest.raises(ValueError, match="soft_llm"):
        _make_verdict(VerdictValue.satisfied, [_soft_step()], parser_provenance)


def test_mixed_evidence_positive_verdict_allowed(parser_provenance) -> None:
    v = _make_verdict(
        VerdictValue.satisfied, [_hard_step(), _soft_step()], parser_provenance
    )
    assert v.verdict == VerdictValue.satisfied


def test_unknown_verdict_no_steps_allowed(parser_provenance) -> None:
    v = _make_verdict(VerdictValue.unknown, [], parser_provenance)
    assert v.verdict == VerdictValue.unknown


def test_risky_verdict_with_only_soft_not_rejected(parser_provenance) -> None:
    v = _make_verdict(VerdictValue.risky, [_soft_step()], parser_provenance)
    assert v.verdict == VerdictValue.risky


def test_process_noncompliant_serializes(parser_provenance) -> None:
    v = _make_verdict(VerdictValue.process_noncompliant, [], parser_provenance)
    from llm_sca_tooling.schemas.base import canonical_dumps

    data = canonical_dumps(v)
    assert b"process-noncompliant" in data


def test_evidence_bundle_only_soft_llm_detection(parser_provenance) -> None:
    item = EvidenceItem(
        evidence_id="e1",
        kind="test",
        supports=EvidenceSupport.supports,
        strength=EvidenceStrength.soft_llm,
        confidence=0.8,
        provenance=parser_provenance,
    )
    bundle = EvidenceBundle(
        bundle_id="b1",
        subject_ref="s1",
        evidence_items=[item],
        aggregate_strength=EvidenceStrength.soft_llm,
        snapshot_consistency=SnapshotConsistency.clean,
        created_ts=NOW,
        provenance=parser_provenance,
    )
    assert bundle.is_only_soft_llm is True
    assert bundle.weakest_strength() == EvidenceStrength.soft_llm


def test_evidence_bundle_empty_is_soft_llm(parser_provenance) -> None:
    bundle = EvidenceBundle(
        bundle_id="b1",
        subject_ref="s1",
        created_ts=NOW,
        provenance=parser_provenance,
    )
    assert bundle.is_only_soft_llm is True
