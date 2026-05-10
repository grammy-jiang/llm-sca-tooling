from __future__ import annotations

from llm_sca_tooling.workflows.impl_check.aggregator import aggregate_clause_verdict
from llm_sca_tooling.workflows.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.workflows.impl_check.models import (
    AggregationMethod,
    ConfidenceLevel,
    DynamicVerdictRecord,
    EvidenceType,
    RiskClass,
    StaticVerdictRecord,
    VerdictValue,
)


def _c():
    return extract_clauses("doc:a", "The `foo` function must work.\n")[0]


def test_stage5_violated_dominates() -> None:
    c = _c()
    s5 = [
        StaticVerdictRecord(
            clause_id=c.clause_id,
            verdict=VerdictValue.VIOLATED,
            evidence_type=EvidenceType.ANALYSER,
            confidence=ConfidenceLevel.ANALYSER,
        )
    ]
    s6a = [
        StaticVerdictRecord(
            clause_id=c.clause_id,
            verdict=VerdictValue.SATISFIED,
            evidence_type=EvidenceType.LLM,
            confidence=ConfidenceLevel.LLM,
        )
    ]
    out = aggregate_clause_verdict(c, s5, s6a, None)
    assert out.final_verdict is VerdictValue.VIOLATED
    assert out.aggregation_method is AggregationMethod.HARD_VIOLATION_DOMINATES


def test_stage6b_violated_dominates() -> None:
    c = _c()
    s6b = DynamicVerdictRecord(
        clause_id=c.clause_id,
        verdict=VerdictValue.VIOLATED,
        confidence=ConfidenceLevel.LLM,
        available=True,
    )
    out = aggregate_clause_verdict(c, [], [], s6b)
    assert out.final_verdict is VerdictValue.VIOLATED


def test_stage5_satisfied_strong_confidence() -> None:
    c = _c()
    s5 = [
        StaticVerdictRecord(
            clause_id=c.clause_id,
            verdict=VerdictValue.SATISFIED,
            evidence_type=EvidenceType.PARSER,
            confidence=ConfidenceLevel.PARSER,
        )
    ]
    out = aggregate_clause_verdict(c, s5, [], None)
    assert out.final_verdict is VerdictValue.SATISFIED


def test_only_stage6a_soft_non_security_no_calibration() -> None:
    c = _c()
    s6a = [
        StaticVerdictRecord(
            clause_id=c.clause_id,
            verdict=VerdictValue.SATISFIED,
            evidence_type=EvidenceType.LLM,
            confidence=ConfidenceLevel.LLM,
        )
    ]
    out = aggregate_clause_verdict(c, [], s6a, None, calibration_ece=None)
    assert out.final_verdict is VerdictValue.UNKNOWN
    assert out.uncertainty_reason


def test_auto_pass_blocked_for_security() -> None:
    c = _c().model_copy(update={"risk_class": RiskClass.SECURITY})
    s6a = [
        StaticVerdictRecord(
            clause_id=c.clause_id,
            verdict=VerdictValue.SATISFIED,
            evidence_type=EvidenceType.LLM,
            confidence=ConfidenceLevel.LLM,
        )
    ]
    out = aggregate_clause_verdict(c, [], s6a, None, calibration_ece=0.05)
    assert out.final_verdict is VerdictValue.UNKNOWN


def test_auto_pass_passes_for_non_security() -> None:
    c = _c()
    s6a = [
        StaticVerdictRecord(
            clause_id=c.clause_id,
            verdict=VerdictValue.SATISFIED,
            evidence_type=EvidenceType.LLM,
            confidence=ConfidenceLevel.LLM,
        )
    ]
    out = aggregate_clause_verdict(c, [], s6a, None, calibration_ece=0.05)
    assert out.final_verdict is VerdictValue.SATISFIED
    assert out.auto_pass_gate_passed


def test_no_evidence_default_unknown() -> None:
    out = aggregate_clause_verdict(_c(), [], [], None)
    assert out.final_verdict is VerdictValue.UNKNOWN
    assert out.aggregation_method is AggregationMethod.DEFAULT_UNKNOWN


def test_calibration_ece_above_threshold_blocks_auto_pass() -> None:
    c = _c()
    s5 = [
        StaticVerdictRecord(
            clause_id=c.clause_id,
            verdict=VerdictValue.SATISFIED,
            evidence_type=EvidenceType.PARSER,
            confidence=ConfidenceLevel.PARSER,
        )
    ]
    out = aggregate_clause_verdict(c, s5, [], None, calibration_ece=0.5)
    assert out.auto_pass_gate_passed is False
