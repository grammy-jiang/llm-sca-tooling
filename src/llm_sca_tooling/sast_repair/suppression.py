"""Suppression-proposal generator for confirmed false positives."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.models import (
    AlertClassification,
    BindingConfidence,
    ClassificationConfidence,
    ClassificationValue,
    SuppressionKind,
    SuppressionProposal,
)


def propose_suppression(
    *,
    classification: AlertClassification,
    rule_id: str,
    file_path: str | None,
    binding_confidence: BindingConfidence,
    git_sha: str | None = None,
    suppression_kind: SuppressionKind = SuppressionKind.INLINE_COMMENT,
    reason: str = "reviewed false positive",
) -> SuppressionProposal | None:
    """Generate a suppression proposal when permitted by classification rules.

    Returns ``None`` when classification rules do not permit a suppression
    (i.e. classification is not ``likely_false_positive`` with at least
    analyser-grade confidence).
    """
    if classification.classification != ClassificationValue.LIKELY_FALSE_POSITIVE:
        return None
    if classification.confidence not in {
        ClassificationConfidence.ANALYSER,
        ClassificationConfidence.PARSER,
    }:
        return None

    if suppression_kind == SuppressionKind.INLINE_COMMENT:
        annotation_text = f"# noqa: {rule_id} - {reason}"
    elif suppression_kind == SuppressionKind.BASELINE_ENTRY:
        if not git_sha:
            raise ValueError("baseline_entry suppressions require git_sha")
        annotation_text = f"baseline-entry rule={rule_id} sha={git_sha} reason={reason}"
    else:
        annotation_text = f"rule-evolution-candidate rule={rule_id} reason={reason}"

    provenance = {
        "binding_confidence": binding_confidence.value,
        "classification_confidence": classification.confidence.value,
        "file_path": file_path,
    }
    return SuppressionProposal(
        alert_id=classification.alert_id,
        rule_id=rule_id,
        classification_ref=f"classification:{classification.alert_id}",
        suppression_kind=suppression_kind,
        annotation_text=annotation_text,
        suppression_scope="alert",
        reviewer_required=True,
        offline_rule_evolution_candidate=(
            suppression_kind == SuppressionKind.RULE_EVOLUTION_CANDIDATE
        ),
        provenance=provenance,
    )


__all__ = ["propose_suppression"]
