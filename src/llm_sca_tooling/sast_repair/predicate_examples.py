"""Predicate example retrieval."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.corpus_adapter import LocalFixtureCorpusAdapter
from llm_sca_tooling.sast_repair.models import PredicateExampleRecord, PredicateMetadata


def get_predicate_examples(
    *,
    metadata: PredicateMetadata,
    adapter: LocalFixtureCorpusAdapter | None = None,
    target_repo_id: str | None = None,
    k: int = 5,
) -> tuple[list[PredicateExampleRecord], list[str]]:
    adapter = adapter or LocalFixtureCorpusAdapter()
    diagnostics: list[str] = []
    examples = adapter.query_by_predicate(
        metadata.rule_id, metadata.negated_predicate_text
    )
    if not examples:
        diagnostics.append("predicate_negation_unavailable")
        examples = adapter.query_by_rule_family(metadata.rule_family)
    if not examples:
        diagnostics.append("embedding_similarity_unavailable")
        examples = adapter.query_by_embedding([], k)
    filtered = [example for example in examples if example.repo_id != target_repo_id]
    return filtered[:k], diagnostics
