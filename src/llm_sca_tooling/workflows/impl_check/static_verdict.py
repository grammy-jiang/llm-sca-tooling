"""Stage 5/6a: Static verdict runner."""

from __future__ import annotations

from llm_sca_tooling.workflows.impl_check.models import (
    CheckabilityValue,
    Clause,
    ClauseGrounding,
    CompileStatus,
    ConfidenceLevel,
    ContractArtifact,
    EvidenceType,
    GroundingMethod,
    RiskClass,
    StaticVerdictRecord,
    VerdictValue,
)


def evaluate_contract(
    clause: Clause,
    artifact: ContractArtifact | None,
    grounding: ClauseGrounding | None,
    sarif_alert_ids: list[str] | None = None,
    test_result_ids: list[str] | None = None,
) -> StaticVerdictRecord:
    sarif_ids = sarif_alert_ids or []
    test_ids = test_result_ids or []

    if clause.checkability is CheckabilityValue.UNVERIFIABLE:
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="5",
            verdict=VerdictValue.UNKNOWN,
            evidence_type=EvidenceType.NONE,
            confidence=ConfidenceLevel.UNKNOWN,
            override_reason="unverifiable_clause",
        )

    if artifact and artifact.compile_status is CompileStatus.FAILED:
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="5",
            verdict=VerdictValue.UNKNOWN,
            evidence_type=EvidenceType.NONE,
            confidence=ConfidenceLevel.UNKNOWN,
            override_reason="contract_compile_failed",
        )

    if sarif_ids:
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="5",
            verdict=VerdictValue.VIOLATED,
            evidence_type=EvidenceType.ANALYSER,
            sarif_alert_ids=sarif_ids,
            confidence=ConfidenceLevel.ANALYSER,
            ece_bucket="high",
        )

    if artifact and artifact.last_run_status is VerdictValue.VIOLATED:
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="5",
            verdict=VerdictValue.VIOLATED,
            evidence_type=EvidenceType.ANALYSER,
            contract_artifact_id=artifact.clause_id,
            confidence=ConfidenceLevel.ANALYSER,
            ece_bucket="high",
        )

    if artifact and artifact.last_run_status is VerdictValue.SATISFIED:
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="5",
            verdict=VerdictValue.SATISFIED,
            evidence_type=EvidenceType.ANALYSER,
            contract_artifact_id=artifact.clause_id,
            confidence=ConfidenceLevel.ANALYSER,
            ece_bucket="low",
        )

    if test_ids:
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="5",
            verdict=VerdictValue.SATISFIED,
            evidence_type=EvidenceType.TEST,
            test_result_ids=test_ids,
            confidence=ConfidenceLevel.TEST,
            ece_bucket="medium",
        )

    if (
        grounding
        and grounding.grounding_method is GroundingMethod.SYMBOL_MATCH
        and grounding.symbol_node_ids
    ):
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="5",
            verdict=VerdictValue.SATISFIED,
            evidence_type=EvidenceType.PARSER,
            graph_path_evidence=list(grounding.symbol_node_ids),
            confidence=ConfidenceLevel.PARSER,
            ece_bucket="medium",
        )

    if (
        grounding
        and grounding.grounding_method is GroundingMethod.DOCUMENT_LINK
        and grounding.document_link_node_ids
    ):
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="5",
            verdict=VerdictValue.SATISFIED,
            evidence_type=EvidenceType.PARSER,
            graph_path_evidence=list(grounding.document_link_node_ids),
            confidence=ConfidenceLevel.HEURISTIC,
            ece_bucket="medium",
        )

    return StaticVerdictRecord(
        clause_id=clause.clause_id,
        stage="5",
        verdict=VerdictValue.UNKNOWN,
        evidence_type=EvidenceType.NONE,
        confidence=ConfidenceLevel.UNKNOWN,
    )


def run_stage_6a_probe(
    clause: Clause,
    grounding: ClauseGrounding,
    stage5_verdict: StaticVerdictRecord,
) -> StaticVerdictRecord | None:
    """Stage 6a soft repo-QA probe.

    Cannot override Stage 5 violated. Security clauses cannot be auto-passed
    by soft evidence alone.
    """
    if stage5_verdict.verdict is VerdictValue.VIOLATED:
        return None
    if stage5_verdict.verdict is not VerdictValue.UNKNOWN:
        return None
    if grounding.grounding_method is not GroundingMethod.REPO_QA:
        return None
    if grounding.confidence < 0.7:
        return None

    if clause.risk_class is RiskClass.SECURITY:
        return StaticVerdictRecord(
            clause_id=clause.clause_id,
            stage="6a",
            verdict=VerdictValue.UNKNOWN,
            evidence_type=EvidenceType.LLM,
            confidence=ConfidenceLevel.LLM,
            override_reason="security_clause_requires_hard_evidence",
        )

    return StaticVerdictRecord(
        clause_id=clause.clause_id,
        stage="6a",
        verdict=VerdictValue.SATISFIED,
        evidence_type=EvidenceType.LLM,
        graph_path_evidence=list(grounding.repo_qa_answer_refs),
        confidence=ConfidenceLevel.LLM,
        ece_bucket="low",
    )
