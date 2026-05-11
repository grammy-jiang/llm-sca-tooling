"""Rule-based alert classification."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.models import AlertBinding, AlertClassification


def classify_alert(
    binding: AlertBinding, *, suppression_history: list[str] | None = None
) -> AlertClassification:
    suppression_history = suppression_history or []
    if suppression_history or "test" in (binding.file_path or ""):
        classification = "likely_false_positive"
        fp = ["reviewed suppression or test-only path"]
        tp: list[str] = []
        confidence = "parser" if suppression_history else "heuristic"
    elif binding.dataflow_path_nodes or binding.rule_family in {
        "injection",
        "nullderef",
    }:
        classification = "likely_true_positive"
        tp = ["security rule family or dataflow evidence"]
        fp = []
        confidence = "analyser"
    else:
        classification = "unknown"
        tp = []
        fp = []
        confidence = "unknown"
    return AlertClassification(
        alert_id=binding.alert_id,
        binding_ref=f"binding:{binding.alert_id}",
        classification=classification,
        tp_evidence=tp,
        fp_evidence=fp,
        confidence=confidence,
        suppression_history=suppression_history,
    )
