"""Repair context builder."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.models import (
    AlertBinding,
    AlertClassification,
    PredicateExampleRecord,
    PredicateMetadata,
    RepairContext,
)


def build_repair_context(
    *,
    binding: AlertBinding,
    classification: AlertClassification,
    metadata: PredicateMetadata,
    examples: list[PredicateExampleRecord],
    budget: int = 4000,
) -> RepairContext:
    explanation = (
        f"{metadata.rule_id}: {metadata.description}. "
        f"Correct pattern: {metadata.negated_predicate_text or 'not available'}."
    )
    token_estimate = len(explanation.split()) + sum(
        len(example.code_snippet.split()) for example in examples
    )
    return RepairContext(
        alert_id=binding.alert_id,
        binding_ref=f"binding:{binding.alert_id}",
        classification_ref=f"classification:{binding.alert_id}",
        graph_slice_ref=f"graph://slice/{binding.file_path or 'unknown'}",
        alert_explanation=explanation,
        predicate_examples_ref=f"predicate://examples/{metadata.rule_id}",
        snapshot_id=binding.graph_snapshot_id,
        language=examples[0].snippet_language if examples else "unknown",
        file_path=binding.file_path,
        span=binding.span,
        context_tokens_estimate=token_estimate,
        budget_remaining=max(0, budget - token_estimate),
        provenance={"classification": classification.classification},
    )
