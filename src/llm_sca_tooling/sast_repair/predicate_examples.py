"""Predicate-example retrieval orchestrator."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.fl.embedding_interface import EmbeddingInterface
from llm_sca_tooling.sast_repair.corpus_adapter import CleanCorpusAdapter
from llm_sca_tooling.sast_repair.models import (
    PredicateExampleRecord,
    PredicateMetadata,
)


def get_predicate_examples(
    *,
    metadata: PredicateMetadata,
    adapter: CleanCorpusAdapter,
    k: int = 5,
    embedding_adapter: EmbeddingInterface | None = None,
) -> tuple[list[PredicateExampleRecord], list[dict[str, Any]]]:
    """Return up to ``k`` predicate examples plus diagnostics.

    Tier 1: ``predicate_negation`` retrieval.
    Tier 2: ``rule_family_match`` when the negated predicate is not available.
    Tier 3: ``embedding_similarity`` when an embedding adapter is available.
    """
    if k <= 0:
        raise ValueError("k must be positive")
    diagnostics: list[dict[str, Any]] = []
    examples: list[PredicateExampleRecord] = []

    if metadata.negated_predicate_text and adapter.supports_predicate_query():
        examples = adapter.query_by_predicate(
            metadata.rule_id, metadata.negated_predicate_text
        )
    else:
        diagnostics.append(
            {"code": "predicate_negation_unavailable", "rule_id": metadata.rule_id}
        )

    if not examples:
        family_examples = adapter.query_by_rule_family(metadata.rule_family)
        if family_examples:
            examples = family_examples
            diagnostics.append(
                {"code": "rule_family_fallback", "rule_id": metadata.rule_id}
            )

    # Tier 3: embedding similarity fallback
    if (
        not examples
        and embedding_adapter is not None
        and embedding_adapter.is_available()
    ):
        try:
            emb = embedding_adapter.embed_text(metadata.rule_id)
            embedding_examples = adapter.query_by_embedding(emb.vector, k)
            if embedding_examples:
                examples = embedding_examples
                diagnostics.append(
                    {
                        "code": "embedding_similarity_fallback",
                        "rule_id": metadata.rule_id,
                    }
                )
        except Exception:
            diagnostics.append(
                {"code": "embedding_similarity_failed", "rule_id": metadata.rule_id}
            )

    if not examples:
        diagnostics.append(
            {"code": "no_predicate_examples", "rule_id": metadata.rule_id}
        )

    truncated = examples[:k]
    diagnostics.append(
        {
            "code": "corpus_freshness",
            "corpus_id": adapter.corpus_id,
            "corpus_version": adapter.corpus_version,
        }
    )
    return truncated, diagnostics


__all__ = ["get_predicate_examples"]
