from __future__ import annotations

from llm_sca_tooling.workflows.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.workflows.impl_check.models import (
    ClauseVerdictRecord,
    OverallComplianceStatus,
    RiskClass,
    VerdictValue,
)
from llm_sca_tooling.workflows.impl_check.verdict_matrix import assemble_verdict_matrix


def _clauses():
    return extract_clauses(
        "doc:m", "The `foo` function must work.\nThe `bar` must encrypt secrets.\n"
    )


def test_assemble_returns_matrix() -> None:
    cs = _clauses()
    records = [
        ClauseVerdictRecord(
            clause_id=cs[0].clause_id, final_verdict=VerdictValue.SATISFIED
        ),
        ClauseVerdictRecord(
            clause_id=cs[1].clause_id, final_verdict=VerdictValue.UNKNOWN
        ),
    ]
    m = assemble_verdict_matrix("doc:m", "run:1", cs, records)
    assert m.clause_count == 2
    assert m.satisfied_count == 1
    assert m.unknown_count == 1
    assert m.violated_count == 0


def test_non_compliant_when_violated() -> None:
    cs = _clauses()
    records = [
        ClauseVerdictRecord(
            clause_id=cs[0].clause_id, final_verdict=VerdictValue.VIOLATED
        ),
        ClauseVerdictRecord(
            clause_id=cs[1].clause_id, final_verdict=VerdictValue.SATISFIED
        ),
    ]
    m = assemble_verdict_matrix("doc:m", "run:1", cs, records)
    assert m.overall_compliance_status is OverallComplianceStatus.NON_COMPLIANT


def test_compliant_when_all_satisfied() -> None:
    cs = _clauses()
    records = [
        ClauseVerdictRecord(clause_id=c.clause_id, final_verdict=VerdictValue.SATISFIED)
        for c in cs
    ]
    m = assemble_verdict_matrix("doc:m", "run:1", cs, records)
    assert m.overall_compliance_status is OverallComplianceStatus.COMPLIANT


def test_unknown_when_all_unknown() -> None:
    cs = _clauses()
    records = [
        ClauseVerdictRecord(clause_id=c.clause_id, final_verdict=VerdictValue.UNKNOWN)
        for c in cs
    ]
    m = assemble_verdict_matrix("doc:m", "run:1", cs, records)
    assert m.overall_compliance_status is OverallComplianceStatus.UNKNOWN


def test_security_clause_verdicts_collected() -> None:
    cs = _clauses()
    sec_clauses = [c for c in cs if c.risk_class is RiskClass.SECURITY]
    assert sec_clauses
    records = [
        ClauseVerdictRecord(clause_id=c.clause_id, final_verdict=VerdictValue.UNKNOWN)
        for c in cs
    ]
    m = assemble_verdict_matrix("doc:m", "run:1", cs, records)
    assert any(
        v["clause_id"] == sec_clauses[0].clause_id for v in m.security_clause_verdicts
    )
