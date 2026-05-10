"""Repair-context builder for Phase 12."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.sast_repair.models import (
    AlertBinding,
    AlertClassification,
    PredicateExampleRecord,
    PredicateMetadata,
    RepairContext,
)

_BUDGET_DEFAULT = 8000


def _explain(
    metadata: PredicateMetadata, examples: list[PredicateExampleRecord]
) -> str:
    parts: list[str] = []
    parts.append(f"Rule: {metadata.rule_id} (family={metadata.rule_family})")
    if metadata.cwe_ids:
        parts.append("CWE: " + ", ".join(metadata.cwe_ids))
    if metadata.description:
        parts.append("What it means: " + metadata.description)
    if metadata.predicate_text:
        parts.append("Why it fired: " + metadata.predicate_text)
    if metadata.fix_guidance:
        parts.append("How to fix: " + metadata.fix_guidance)
    if examples:
        sources = sorted({rec.retrieval_method.value for rec in examples})
        parts.append(
            f"Fix-knowledge: {len(examples)} example(s); methods={','.join(sources)}"
        )
    else:
        parts.append("Fix-knowledge: no predicate examples available")
    return "\n".join(parts)


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def build_repair_context(
    *,
    binding: AlertBinding,
    classification: AlertClassification,
    metadata: PredicateMetadata,
    examples: list[PredicateExampleRecord],
    graph_slice_ref: str | None = None,
    interface_contracts_ref: list[str] | None = None,
    language: str | None = None,
    snapshot_id: str | None = None,
    budget: int = _BUDGET_DEFAULT,
) -> RepairContext:
    """Assemble a :class:`RepairContext` while respecting the token budget."""
    explanation = _explain(metadata, examples)
    file_path = binding.file_path
    span = binding.span

    tokens = _estimate_tokens(explanation)
    tokens += _estimate_tokens(metadata.description or "")
    used_examples: list[str] = []
    for record in examples:
        cost = _estimate_tokens(record.code_snippet)
        if tokens + cost > budget:
            break
        tokens += cost
        used_examples.append(f"example:{record.example_id}")

    provenance: dict[str, Any] = {
        "binding_confidence": binding.confidence.value,
        "classification": classification.classification.value,
        "predicate_source": metadata.source,
        "examples_total": len(examples),
        "examples_included": len(used_examples),
    }
    if budget < tokens:
        provenance["budget_event"] = "budget_exhausted"
    return RepairContext(
        alert_id=binding.alert_id,
        binding_ref=f"binding:{binding.alert_id}",
        classification_ref=f"classification:{binding.alert_id}",
        graph_slice_ref=graph_slice_ref,
        alert_explanation=explanation,
        predicate_examples_ref=used_examples,
        interface_contracts_ref=list(interface_contracts_ref or []),
        snapshot_id=snapshot_id,
        language=language,
        file_path=file_path,
        span=span,
        context_tokens_estimate=tokens,
        budget_remaining=max(budget - tokens, 0),
        provenance=provenance,
    )


__all__ = ["build_repair_context"]
