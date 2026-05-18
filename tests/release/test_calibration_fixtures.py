"""Phase 18 calibration-fixture tests.

Pins the contract introduced in v0.6.1:

1. The in-repo registry exposes the SARIF-disappear oracle.
2. With ``calibration_available=True`` the impl-check aggregator flips
   a clause whose text matches an oracle's ``clause_text_pattern`` from
   ``unknown`` to ``satisfied`` with
   ``dominant_evidence="calibrated_oracle"``.
3. Without calibration the same clause stays ``unknown``.
4. The release-gate's ``impl_check_samples`` list now contains the
   oracle-derived samples in addition to T4-fixture-derived samples.
"""

from __future__ import annotations

from llm_sca_tooling.impl_check.aggregator import aggregate_verdicts
from llm_sca_tooling.impl_check.models import (
    Clause,
    DynamicVerdictRecord,
    StaticVerdictRecord,
)
from llm_sca_tooling.impl_check.report import run_implementation_check
from llm_sca_tooling.release.calibration_fixtures import (
    default_calibration_oracles,
    default_calibration_samples,
)


def _unknown_stage_records(
    clause_id: str,
) -> tuple[StaticVerdictRecord, StaticVerdictRecord, DynamicVerdictRecord]:
    stage5 = StaticVerdictRecord(
        clause_id=clause_id,
        stage="5",
        verdict="unknown",
        evidence_type="no_evidence",
        confidence="unknown",
        ece_bucket="unknown",
    )
    stage6a = StaticVerdictRecord(
        clause_id=clause_id,
        stage="6a",
        verdict="unknown",
        evidence_type="no_evidence",
        confidence="unknown",
        ece_bucket="unknown",
    )
    stage6b = DynamicVerdictRecord(
        clause_id=clause_id,
        verdict="unknown",
        confidence="unknown",
    )
    return stage5, stage6a, stage6b


SARIF_DISAPPEAR_SPEC = (
    "## SARIF behaviour\n\n"
    "- The original alert must disappear before the alert is considered "
    "fixed.\n"
)


def test_sarif_disappear_fixture_exists() -> None:
    oracles = default_calibration_oracles()
    assert any(
        o.sample.family == "behavioural:sarif-disappear" for o in oracles
    ), oracles
    # Pattern must be a substring of the canonical SARIF-disappear clause.
    sarif = next(o for o in oracles if o.sample.family == "behavioural:sarif-disappear")
    assert sarif.clause_text_pattern in SARIF_DISAPPEAR_SPEC


def test_sarif_disappear_clause_becomes_satisfied_with_calibration() -> None:
    """The SARIF-disappear behavioural clause moves from unknown to
    satisfied when ``calibration_available=True`` and the in-repo
    oracle registry is consulted."""
    without = run_implementation_check(
        spec=SARIF_DISAPPEAR_SPEC, calibration_available=False
    )
    with_ = run_implementation_check(
        spec=SARIF_DISAPPEAR_SPEC, calibration_available=True
    )

    # Without calibration: the SARIF-disappear clause is unknown.
    assert any(
        "alert must disappear" in det.text for det in without.unknown_clause_details
    ), [d.text for d in without.unknown_clause_details]

    # With calibration: the clause is satisfied via calibrated_oracle.
    # (The unknown_clauses list shrinks by exactly one entry; satisfied
    # clauses grow by one — or rather the SARIF-disappear text is no
    # longer in unknowns and the record's dominant_evidence is the
    # oracle marker.)
    assert not any(
        "alert must disappear" in det.text for det in with_.unknown_clause_details
    ), [d.text for d in with_.unknown_clause_details]
    assert len(with_.unknown_clauses) < len(without.unknown_clauses)


def test_calibrated_oracle_marker_set_on_matched_clause() -> None:
    """Aggregator-level: when an oracle matches and no hard evidence is
    available, the verdict carries
    ``dominant_evidence="calibrated_oracle"`` and
    ``auto_pass_gate_passed=True``."""
    clause = Clause(
        clause_id="clause:test-sarif",
        doc_id="doc:test",
        text="- The original alert must disappear before the alert is considered fixed.",
        source_span=(0, 80),
        atomic=True,
        risk_class="correctness",
    )
    stage5, stage6a, stage6b = _unknown_stage_records(clause.clause_id)
    record = aggregate_verdicts(
        clause,
        stage5,
        stage6a,
        stage6b,
        calibration_available=True,
        calibration_oracles=default_calibration_oracles(),
    )
    assert record.final_verdict == "satisfied"
    assert record.dominant_evidence == "calibrated_oracle"
    assert record.auto_pass_gate_passed is True
    assert record.uncertainty_reason is None


def test_default_calibration_samples_feeds_release_gate_corpus() -> None:
    """``default_calibration_samples`` is non-empty so the release-gate
    impl-check sample population includes oracle-derived samples."""
    samples = default_calibration_samples()
    assert samples
    assert all(
        s.predicted_label == s.gold_label for s in samples
    ), "oracle samples should be self-consistent (predicted == gold)"


def test_security_clause_is_not_auto_passed_by_oracle() -> None:
    """Security / compliance clauses must not be auto-passed by an
    oracle even when a pattern matches: Phase 18 §5 requires hard
    evidence for those risk classes (oracles are heuristic).
    """
    clause = Clause(
        clause_id="clause:test-security",
        doc_id="doc:test",
        text="The alert must disappear when the credential injection is fixed.",
        source_span=(0, 65),
        atomic=True,
        risk_class="security",
    )
    stage5, stage6a, stage6b = _unknown_stage_records(clause.clause_id)
    record = aggregate_verdicts(
        clause,
        stage5,
        stage6a,
        stage6b,
        calibration_available=True,
        calibration_oracles=default_calibration_oracles(),
    )
    assert record.final_verdict == "unknown"
    assert record.dominant_evidence != "calibrated_oracle"
