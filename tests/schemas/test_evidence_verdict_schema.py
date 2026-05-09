from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.schemas.enums import EvidenceStrength, PolicyAction, SnapshotConsistency, VerdictValue
from llm_sca_tooling.schemas.evidence import EvidenceBundle, EvidenceItem, EvidenceSupport, MissingEvidence, StaleEvidence
from llm_sca_tooling.schemas.provenance import Provenance
from llm_sca_tooling.schemas.verdicts import CalibrationRef, ReasoningStep, Uncertainty, Verdict, validate_verdict_against_bundle

TS = "2026-05-09T00:00:00Z"


def soft_bundle(provenance: Provenance) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="bundle:soft",
        subject_ref="node:f1",
        evidence_items=[
            EvidenceItem(
                evidence_id="evidence:llm",
                kind="summary",
                supports=EvidenceSupport.SUPPORTS,
                strength=EvidenceStrength.SOFT_LLM,
                confidence=0.9,
                provenance=provenance,
            )
        ],
        missing_evidence=[MissingEvidence(missing_id="missing:test", expected_kind="test", reason="not run")],
        stale_evidence=[StaleEvidence(stale_id="stale:index", evidence_ref="graph:old", reason="old snapshot")],
        aggregate_strength=EvidenceStrength.SOFT_LLM,
        snapshot_consistency=SnapshotConsistency.UNKNOWN,
        created_ts=TS,
        provenance=provenance,
    )


def test_evidence_bundle_separates_evidence(provenance: Provenance) -> None:
    bundle = soft_bundle(provenance)
    assert len(bundle.evidence_items) == 1
    assert bundle.missing_evidence[0].expected_kind == "test"
    assert bundle.stale_evidence[0].evidence_ref == "graph:old"


def test_positive_verdict_with_only_soft_llm_evidence_fails(provenance: Provenance) -> None:
    bundle = soft_bundle(provenance)
    verdict = Verdict(
        verdict_id="verdict:safe",
        workflow="patch-review",
        subject_ref="patch:1",
        verdict=VerdictValue.SAFE,
        confidence=0.8,
        evidence_bundle_id=bundle.bundle_id,
        recommended_action="merge",
        policy_action=PolicyAction.ALLOW,
        provenance=provenance,
    )
    with pytest.raises(ValueError):
        validate_verdict_against_bundle(verdict, bundle)


def test_unknown_verdict_requires_uncertainty(provenance: Provenance) -> None:
    with pytest.raises(ValidationError):
        Verdict(
            verdict_id="verdict:unknown",
            workflow="repo-qa",
            subject_ref="node:f1",
            verdict=VerdictValue.UNKNOWN,
            confidence=0.0,
            evidence_bundle_id="bundle:1",
            recommended_action="collect evidence",
            policy_action=PolicyAction.FORCE_UNKNOWN,
            provenance=provenance,
        )
    ok = Verdict(
        verdict_id="verdict:unknown",
        workflow="repo-qa",
        subject_ref="node:f1",
        verdict=VerdictValue.UNKNOWN,
        confidence=0.0,
        evidence_bundle_id="bundle:1",
        uncertainty=[Uncertainty(kind="missing", description="tests unavailable", forces_unknown=True)],
        recommended_action="collect evidence",
        policy_action=PolicyAction.FORCE_UNKNOWN,
        provenance=provenance,
    )
    assert ok.verdict == VerdictValue.UNKNOWN


def test_calibrated_reasoning_requires_calibration(provenance: Provenance) -> None:
    step = ReasoningStep(step_id="step:1", claim="model predicts safe", strength=EvidenceStrength.CALIBRATED_MODEL)
    with pytest.raises(ValidationError):
        Verdict(
            verdict_id="verdict:model",
            workflow="patch-review",
            subject_ref="patch:1",
            verdict=VerdictValue.RISKY,
            confidence=0.6,
            evidence_bundle_id="bundle:1",
            reasoning_chain=[step],
            recommended_action="review",
            policy_action=PolicyAction.APPROVAL_REQUIRED,
            provenance=provenance,
        )
    assert CalibrationRef(calibration_id="cal:1", family="python", version="0.1").family == "python"
