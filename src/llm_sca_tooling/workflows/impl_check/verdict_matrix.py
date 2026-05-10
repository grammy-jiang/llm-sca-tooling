"""Stage 7: ClauseVerdictMatrix assembler."""

from __future__ import annotations

from datetime import UTC, datetime

from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.workflows.impl_check.models import (
    Clause,
    ClauseVerdictMatrix,
    ClauseVerdictRecord,
    OverallComplianceStatus,
    RiskClass,
    VerdictValue,
)


def assemble_verdict_matrix(
    doc_id: str,
    run_id: str,
    clauses: list[Clause],
    verdict_records: list[ClauseVerdictRecord],
) -> ClauseVerdictMatrix:
    satisfied = [
        r for r in verdict_records if r.final_verdict is VerdictValue.SATISFIED
    ]
    violated = [r for r in verdict_records if r.final_verdict is VerdictValue.VIOLATED]
    unknown = [r for r in verdict_records if r.final_verdict is VerdictValue.UNKNOWN]

    if violated:
        overall = OverallComplianceStatus.NON_COMPLIANT
    elif unknown and not satisfied:
        overall = OverallComplianceStatus.UNKNOWN
    elif unknown:
        overall = OverallComplianceStatus.PARTIALLY_COMPLIANT
    elif satisfied:
        overall = OverallComplianceStatus.COMPLIANT
    else:
        overall = OverallComplianceStatus.UNKNOWN

    clause_by_id = {c.clause_id: c for c in clauses}
    security_verdicts: list[JsonObject] = []
    harness_verdicts: list[JsonObject] = []

    for r in verdict_records:
        clause = clause_by_id.get(r.clause_id)
        if clause is None:
            continue
        if clause.risk_class is RiskClass.SECURITY:
            security_verdicts.append(
                {"clause_id": r.clause_id, "verdict": r.final_verdict.value}
            )
        if clause.harness_policy_flag:
            harness_verdicts.append(
                {"clause_id": r.clause_id, "verdict": r.final_verdict.value}
            )

    return ClauseVerdictMatrix(
        doc_id=doc_id,
        run_id=run_id,
        clause_count=len(verdict_records),
        satisfied_count=len(satisfied),
        violated_count=len(violated),
        unknown_count=len(unknown),
        security_clause_verdicts=security_verdicts,
        harness_policy_verdicts=harness_verdicts,
        per_clause_records=[r.model_dump(mode="json") for r in verdict_records],
        overall_compliance_status=overall,
        created_ts=datetime.now(UTC).isoformat(),
    )
