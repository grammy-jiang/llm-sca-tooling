"""Stage 7: Verdict aggregator with priority-dominance rules."""

from __future__ import annotations

from llm_sca_tooling.impl_check.models import (
    Clause,
    ClauseVerdictRecord,
    DynamicVerdictRecord,
    HarnessPolicyClause,
    StaticVerdictRecord,
)

_HARD_CONFIDENCE = {"analyser", "parser", "test"}


def aggregate_verdicts(
    clause: Clause | HarnessPolicyClause,
    stage5: StaticVerdictRecord,
    stage6a: StaticVerdictRecord,
    stage6b: DynamicVerdictRecord,
    *,
    calibration_available: bool = False,
) -> ClauseVerdictRecord:
    # Rule 1: any Stage 5 violated is final
    if stage5.verdict == "violated":
        return ClauseVerdictRecord(
            clause_id=clause.clause_id,
            final_verdict="violated",
            confidence=stage5.confidence,
            ece_bucket=stage5.ece_bucket,
            stage_5_verdicts=[stage5.verdict],
            stage_6a_verdicts=[stage6a.verdict],
            stage_6b_verdict=stage6b.verdict,
            dominant_evidence=f"stage5:{stage5.evidence_type}",
            auto_pass_gate_passed=False,
        )

    # Rule 2: any Stage 6b violated is final
    if stage6b.verdict == "violated":
        return ClauseVerdictRecord(
            clause_id=clause.clause_id,
            final_verdict="violated",
            confidence=stage6b.confidence,
            ece_bucket="unknown",
            stage_5_verdicts=[stage5.verdict],
            stage_6a_verdicts=[stage6a.verdict],
            stage_6b_verdict=stage6b.verdict,
            dominant_evidence="stage6b:dynamic_trace",
            auto_pass_gate_passed=False,
        )

    # Auto-pass gate
    auto_pass = (
        calibration_available
        and stage5.verdict == "satisfied"
        and stage5.confidence in _HARD_CONFIDENCE
        and clause.risk_class not in {"security", "compliance"}
    )

    # Rule 3: Stage 5 satisfied with hard confidence
    if stage5.verdict == "satisfied" and stage5.confidence in _HARD_CONFIDENCE:
        final = "satisfied" if auto_pass else "satisfied"
        return ClauseVerdictRecord(
            clause_id=clause.clause_id,
            final_verdict=final,
            confidence=stage5.confidence,
            ece_bucket=stage5.ece_bucket,
            stage_5_verdicts=[stage5.verdict],
            stage_6a_verdicts=[stage6a.verdict],
            stage_6b_verdict=stage6b.verdict,
            dominant_evidence=f"stage5:{stage5.evidence_type}",
            auto_pass_gate_passed=auto_pass,
        )

    # Rule 4: only soft evidence or unknown
    uncertainty = None
    if not calibration_available:
        uncertainty = "calibration_absent"
    elif clause.risk_class in {"security", "compliance"}:
        uncertainty = "security_or_compliance_requires_hard_evidence"

    # Stage 5 satisfied with heuristic confidence
    if stage5.verdict == "satisfied":
        return ClauseVerdictRecord(
            clause_id=clause.clause_id,
            final_verdict="satisfied",
            confidence="heuristic",
            ece_bucket="medium_confidence",
            stage_5_verdicts=[stage5.verdict],
            stage_6a_verdicts=[stage6a.verdict],
            stage_6b_verdict=stage6b.verdict,
            dominant_evidence=f"stage5:{stage5.evidence_type}",
            auto_pass_gate_passed=False,
            uncertainty_reason=uncertainty,
        )

    return ClauseVerdictRecord(
        clause_id=clause.clause_id,
        final_verdict="unknown",
        confidence="unknown",
        ece_bucket="unknown",
        stage_5_verdicts=[stage5.verdict],
        stage_6a_verdicts=[stage6a.verdict],
        stage_6b_verdict=stage6b.verdict,
        dominant_evidence="no_hard_evidence",
        auto_pass_gate_passed=False,
        uncertainty_reason=uncertainty or "insufficient_evidence",
    )
