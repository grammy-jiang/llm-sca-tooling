"""Suppression proposal generation."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.models import AlertClassification, SuppressionProposal


def propose_suppression(
    *, classification: AlertClassification, rule_id: str
) -> SuppressionProposal | None:
    if (
        classification.classification != "likely_false_positive"
        or classification.confidence
        not in {
            "parser",
            "analyser",
        }
    ):
        return None
    return SuppressionProposal(
        alert_id=classification.alert_id,
        rule_id=rule_id,
        classification_ref=classification.binding_ref,
        suppression_kind="inline_comment",
        annotation_text=f"suppress {rule_id}: reviewed false positive",
        suppression_scope="alert-location",
        reviewer_required=True,
        offline_rule_evolution_candidate=True,
        provenance={"phase": "12"},
    )
