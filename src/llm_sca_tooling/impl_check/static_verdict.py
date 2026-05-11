"""Stage 5 and 6a: Static verdict runner and repo-QA probe."""

from __future__ import annotations

from llm_sca_tooling.impl_check.models import (
    Clause,
    ClauseGrounding,
    HarnessPolicyClause,
    ImplContractArtifact,
    StaticVerdictRecord,
)


def run_static_verdict(
    clause: Clause | HarnessPolicyClause,
    grounding: ClauseGrounding,
    artifact: ImplContractArtifact,
    *,
    simulate_violation: bool = False,
    simulate_harness_policy_violation: bool = False,
) -> StaticVerdictRecord:
    # Harness-policy clause: check for required gate events
    if isinstance(clause, HarnessPolicyClause) or clause.harness_policy_flag:
        if simulate_harness_policy_violation:
            return StaticVerdictRecord(
                clause_id=clause.clause_id,
                stage="5",
                verdict="violated",
                evidence_type="harness_policy_gate_missing",
                contract_artifact_id=artifact.artifact_id,
                confidence="analyser",
                ece_bucket="high_confidence",
                override_reason="required gate event absent",
            )
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="5",
            verdict="satisfied",
            evidence_type="harness_policy_gate_present",
            contract_artifact_id=artifact.artifact_id,
            confidence="analyser",
            ece_bucket="high_confidence",
        )

    # Simulated violation (e.g., Semgrep rule fires)
    if simulate_violation:
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="5",
            verdict="violated",
            evidence_type="semgrep_predicate_fired",
            contract_artifact_id=artifact.artifact_id,
            confidence="analyser",
            ece_bucket="high_confidence",
        )

    # Ungrounded → unknown
    if grounding.grounding_method == "ungrounded":
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="5",
            verdict="unknown",
            evidence_type="missing_grounding",
            contract_artifact_id=artifact.artifact_id,
            confidence="unknown",
            ece_bucket="unknown",
        )

    # Grounded + compiled artifact → satisfied
    if artifact.compile_status in {"passed", "not_applicable"}:
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="5",
            verdict="satisfied",
            evidence_type="graph_path_grounded",
            contract_artifact_id=artifact.artifact_id,
            graph_path_evidence=grounding.symbol_node_ids[:2],
            confidence="heuristic",
            ece_bucket="medium_confidence",
        )

    return StaticVerdictRecord(
        clause_id=clause.clause_id,
        stage="5",
        verdict="unknown",
        evidence_type="no_static_evidence",
        contract_artifact_id=artifact.artifact_id,
        confidence="unknown",
        ece_bucket="unknown",
    )


def run_stage_6a_probe(
    clause: Clause | HarnessPolicyClause,
    stage5: StaticVerdictRecord,
    *,
    simulate_security_clause: bool = False,
) -> StaticVerdictRecord:
    """Stage 6a repo-QA soft probe. Cannot override a Stage 5 violated verdict."""
    if stage5.verdict == "violated":
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="6a",
            verdict="violated",
            evidence_type="inherited_from_stage5",
            confidence=stage5.confidence,
            ece_bucket=stage5.ece_bucket,
            override_reason="stage5_violated_is_final",
        )
    # Security clauses: soft answers cannot auto-pass
    if clause.risk_class == "security" or simulate_security_clause:
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="6a",
            verdict="unknown",
            evidence_type="security_clause_soft_answer_blocked",
            confidence="llm",
            ece_bucket="unknown",
        )
    if stage5.verdict == "unknown":
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="6a",
            verdict="unknown",
            evidence_type="repo_qa_soft_support",
            confidence="llm",
            ece_bucket="unknown",
        )
    return StaticVerdictRecord(
        clause_id=clause.clause_id,
        stage="6a",
        verdict=stage5.verdict,
        evidence_type="stage5_carried_forward",
        confidence=stage5.confidence,
        ece_bucket=stage5.ece_bucket,
    )
