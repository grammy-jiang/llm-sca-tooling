"""Clause verdict matrix assembler."""

from __future__ import annotations

from llm_sca_tooling.impl_check.models import (
    Clause,
    ClauseVerdictMatrix,
    ClauseVerdictRecord,
    HarnessPolicyClause,
)


def build_verdict_matrix(
    doc_id: str,
    run_id: str,
    clauses: list[Clause | HarnessPolicyClause],
    records: list[ClauseVerdictRecord],
) -> ClauseVerdictMatrix:
    satisfied = [r for r in records if r.final_verdict == "satisfied"]
    violated = [r for r in records if r.final_verdict == "violated"]
    unknown = [r for r in records if r.final_verdict == "unknown"]

    security = [
        {"clause_id": c.clause_id, "verdict": _verdict_for(c.clause_id, records)}
        for c in clauses
        if c.risk_class == "security"
    ]
    policy = [
        {"clause_id": c.clause_id, "verdict": _verdict_for(c.clause_id, records)}
        for c in clauses
        if c.harness_policy_flag
    ]

    if violated:
        status = "non_compliant"
    elif unknown and not satisfied:
        status = "unknown"
    elif unknown:
        status = "partially_compliant"
    else:
        status = "compliant"

    return ClauseVerdictMatrix(
        doc_id=doc_id,
        run_id=run_id,
        clause_count=len(clauses),
        satisfied_count=len(satisfied),
        violated_count=len(violated),
        unknown_count=len(unknown),
        security_clause_verdicts=security,
        harness_policy_verdicts=policy,
        per_clause_records=records,
        overall_compliance_status=status,
    )


def _verdict_for(clause_id: str, records: list[ClauseVerdictRecord]) -> str:
    for r in records:
        if r.clause_id == clause_id:
            return r.final_verdict
    return "unknown"
