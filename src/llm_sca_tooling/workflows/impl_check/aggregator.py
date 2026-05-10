"""Stage 7: Verdict aggregator."""

from __future__ import annotations

from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.workflows.impl_check.models import (
    AggregationMethod,
    Clause,
    ClauseVerdictRecord,
    ConfidenceLevel,
    DynamicVerdictRecord,
    RiskClass,
    StaticVerdictRecord,
    VerdictValue,
)

_HIGH_STAKES_RISK_CLASSES = {RiskClass.SECURITY, RiskClass.COMPLIANCE}
_STRONG_CONFIDENCE = {
    ConfidenceLevel.ANALYSER,
    ConfidenceLevel.PARSER,
    ConfidenceLevel.TEST,
}


def _sv_to_dict(v: StaticVerdictRecord) -> JsonObject:
    return v.model_dump(mode="json")


def _dv_to_dict(v: DynamicVerdictRecord | None) -> JsonObject | None:
    return v.model_dump(mode="json") if v is not None else None


def _check_auto_pass(clause: Clause, calibration_ece: float | None) -> bool:
    if calibration_ece is None:
        return False
    if calibration_ece > 0.10:
        return False
    if clause.risk_class in _HIGH_STAKES_RISK_CLASSES:
        return False
    return True


def aggregate_clause_verdict(
    clause: Clause,
    stage5_verdicts: list[StaticVerdictRecord],
    stage6a_verdicts: list[StaticVerdictRecord],
    stage6b_verdict: DynamicVerdictRecord | None,
    *,
    calibration_ece: float | None = None,
    calibration_family: str | None = None,
) -> ClauseVerdictRecord:
    s5_dicts = [_sv_to_dict(s) for s in stage5_verdicts]
    s6a_dicts = [_sv_to_dict(s) for s in stage6a_verdicts]
    s6b_dict = _dv_to_dict(stage6b_verdict)

    for v in stage5_verdicts:
        if v.verdict is VerdictValue.VIOLATED:
            return ClauseVerdictRecord(
                clause_id=clause.clause_id,
                final_verdict=VerdictValue.VIOLATED,
                confidence=v.confidence,
                ece_bucket=v.ece_bucket,
                stage_5_verdicts=s5_dicts,
                stage_6a_verdicts=s6a_dicts,
                stage_6b_verdict=s6b_dict,
                dominant_evidence=f"stage5:{v.evidence_type.value}",
                aggregation_method=AggregationMethod.HARD_VIOLATION_DOMINATES,
                auto_pass_gate_passed=False,
                calibration_family=calibration_family,
            )

    if stage6b_verdict and stage6b_verdict.verdict is VerdictValue.VIOLATED:
        return ClauseVerdictRecord(
            clause_id=clause.clause_id,
            final_verdict=VerdictValue.VIOLATED,
            confidence=stage6b_verdict.confidence,
            ece_bucket=None,
            stage_5_verdicts=s5_dicts,
            stage_6a_verdicts=s6a_dicts,
            stage_6b_verdict=s6b_dict,
            dominant_evidence="stage6b:dynamic_trace",
            aggregation_method=AggregationMethod.HARD_VIOLATION_DOMINATES,
            auto_pass_gate_passed=False,
            calibration_family=calibration_family,
        )

    strong_satisfied = [
        v
        for v in stage5_verdicts
        if v.verdict is VerdictValue.SATISFIED and v.confidence in _STRONG_CONFIDENCE
    ]
    if strong_satisfied:
        auto_pass = _check_auto_pass(clause, calibration_ece)
        chosen = strong_satisfied[0]
        return ClauseVerdictRecord(
            clause_id=clause.clause_id,
            final_verdict=VerdictValue.SATISFIED,
            confidence=chosen.confidence,
            ece_bucket=chosen.ece_bucket,
            stage_5_verdicts=s5_dicts,
            stage_6a_verdicts=s6a_dicts,
            stage_6b_verdict=s6b_dict,
            dominant_evidence=f"stage5:{chosen.evidence_type.value}",
            aggregation_method=(
                AggregationMethod.AUTO_PASS
                if auto_pass
                else AggregationMethod.SOFT_CONSENSUS
            ),
            auto_pass_gate_passed=auto_pass,
            calibration_family=calibration_family,
        )

    for v in stage6a_verdicts:
        if v.verdict is VerdictValue.SATISFIED:
            is_high_stakes = clause.risk_class in _HIGH_STAKES_RISK_CLASSES
            auto_pass = _check_auto_pass(clause, calibration_ece)
            if is_high_stakes or not auto_pass:
                return ClauseVerdictRecord(
                    clause_id=clause.clause_id,
                    final_verdict=VerdictValue.UNKNOWN,
                    confidence=ConfidenceLevel.LLM,
                    ece_bucket=None,
                    stage_5_verdicts=s5_dicts,
                    stage_6a_verdicts=s6a_dicts,
                    stage_6b_verdict=s6b_dict,
                    dominant_evidence="stage6a:soft",
                    aggregation_method=AggregationMethod.DEFAULT_UNKNOWN,
                    auto_pass_gate_passed=False,
                    calibration_family=calibration_family,
                    uncertainty_reason="high_stakes_or_no_calibration",
                )
            return ClauseVerdictRecord(
                clause_id=clause.clause_id,
                final_verdict=VerdictValue.SATISFIED,
                confidence=ConfidenceLevel.LLM,
                ece_bucket=v.ece_bucket,
                stage_5_verdicts=s5_dicts,
                stage_6a_verdicts=s6a_dicts,
                stage_6b_verdict=s6b_dict,
                dominant_evidence="stage6a:soft",
                aggregation_method=AggregationMethod.SOFT_CONSENSUS,
                auto_pass_gate_passed=auto_pass,
                calibration_family=calibration_family,
            )

    return ClauseVerdictRecord(
        clause_id=clause.clause_id,
        final_verdict=VerdictValue.UNKNOWN,
        confidence=ConfidenceLevel.UNKNOWN,
        ece_bucket=None,
        stage_5_verdicts=s5_dicts,
        stage_6a_verdicts=s6a_dicts,
        stage_6b_verdict=s6b_dict,
        dominant_evidence="none",
        aggregation_method=AggregationMethod.DEFAULT_UNKNOWN,
        auto_pass_gate_passed=False,
        calibration_family=calibration_family,
        uncertainty_reason="no_evidence",
    )
