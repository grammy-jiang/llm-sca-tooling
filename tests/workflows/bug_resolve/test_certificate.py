"""Tests for execution-free certificate builder."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.certificate import build_certificate
from llm_sca_tooling.workflows.bug_resolve.models import CertificateConclusion


def test_supported_conclusion() -> None:
    c = build_certificate(
        run_id="r1",
        candidate_index=0,
        premises=["P"],
        path_claims=["fix"],
        confidence=0.7,
    )
    assert c.conclusion is CertificateConclusion.SUPPORTED


def test_unsupported_counterexample() -> None:
    c = build_certificate(
        run_id="r1",
        candidate_index=0,
        premises=["P"],
        counterexample_found=True,
    )
    assert c.conclusion is CertificateConclusion.UNSUPPORTED


def test_partially_supported() -> None:
    c = build_certificate(
        run_id="r1",
        candidate_index=0,
        premises=["P"],
        unsupported_claims=["Q unverified"],
    )
    assert c.conclusion is CertificateConclusion.PARTIALLY_SUPPORTED


def test_unknown_no_premises() -> None:
    c = build_certificate(run_id="r1", candidate_index=0)
    assert c.conclusion is CertificateConclusion.UNKNOWN


def test_confidence_clamped() -> None:
    c = build_certificate(
        run_id="r1", candidate_index=0, premises=["P"], confidence=2.0
    )
    assert c.confidence == 1.0
