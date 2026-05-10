"""Alert classification (TP/FP/unknown) for Phase 12."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.sast_repair.models import (
    AlertBinding,
    AlertClassification,
    BindingConfidence,
    ClassificationConfidence,
    ClassificationValue,
)


def _binding_ref(binding: AlertBinding) -> str:
    return f"binding:{binding.alert_id}"


def classify_alert(
    *,
    binding: AlertBinding,
    has_dataflow_edges: bool = False,
    security_sensitive_symbol: bool = False,
    similar_pattern_in_repo: bool = False,
    suppression_comment_present: bool = False,
    test_only_symbol: bool = False,
    high_fp_rule: bool = False,
    historical_suppressions: list[dict[str, Any]] | None = None,
    diagnostics: list[dict[str, Any]] | None = None,
) -> AlertClassification:
    """Classify an alert from binding + structured project signals."""
    history = list(historical_suppressions or [])
    diags = list(diagnostics or [])
    tp_evidence: list[str] = []
    fp_evidence: list[str] = []

    if has_dataflow_edges and binding.confidence == BindingConfidence.PARSER:
        tp_evidence.append("dataflow_path_parser_confirmed")
    if security_sensitive_symbol:
        tp_evidence.append("security_sensitive_symbol")
    if similar_pattern_in_repo:
        tp_evidence.append("similar_pattern_in_repo")
    if not suppression_comment_present:
        tp_evidence.append("no_suppression_comment")

    if not has_dataflow_edges and binding.confidence == BindingConfidence.PARSER:
        fp_evidence.append("dataflow_unreachable_parser_confirmed")
    if high_fp_rule:
        fp_evidence.append("rule_known_high_fp_rate")
    if test_only_symbol:
        fp_evidence.append("test_only_symbol")
    if history:
        fp_evidence.append("previously_suppressed_with_reason")

    classification: ClassificationValue
    confidence: ClassificationConfidence
    if fp_evidence and len(fp_evidence) > len(tp_evidence):
        classification = ClassificationValue.LIKELY_FALSE_POSITIVE
        if "dataflow_unreachable_parser_confirmed" in fp_evidence:
            confidence = ClassificationConfidence.PARSER
        elif binding.confidence == BindingConfidence.ANALYSER:
            confidence = ClassificationConfidence.ANALYSER
        else:
            confidence = ClassificationConfidence.HEURISTIC
    elif tp_evidence and (not fp_evidence or len(tp_evidence) > len(fp_evidence)):
        classification = ClassificationValue.LIKELY_TRUE_POSITIVE
        if "dataflow_path_parser_confirmed" in tp_evidence:
            confidence = ClassificationConfidence.PARSER
        elif binding.confidence == BindingConfidence.ANALYSER:
            confidence = ClassificationConfidence.ANALYSER
        else:
            confidence = ClassificationConfidence.HEURISTIC
    else:
        classification = ClassificationValue.UNKNOWN
        confidence = ClassificationConfidence.UNKNOWN
        diags.append({"code": "insufficient_evidence", "alert_id": binding.alert_id})

    return AlertClassification(
        alert_id=binding.alert_id,
        binding_ref=_binding_ref(binding),
        classification=classification,
        tp_evidence=tp_evidence,
        fp_evidence=fp_evidence,
        confidence=confidence,
        calibrated=False,
        suppression_history=history,
        diagnostics=diags,
    )


__all__ = ["classify_alert"]
