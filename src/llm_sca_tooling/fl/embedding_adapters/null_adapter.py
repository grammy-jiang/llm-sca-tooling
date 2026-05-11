"""Null embedding adapter used in CI and budget mode."""

from __future__ import annotations

from llm_sca_tooling.fl.embedding_interface import (
    EmbeddingUnavailable,
    EmbeddingVector,
    cosine,
)

__all__ = ["NullEmbeddingAdapter"]


class NullEmbeddingAdapter:
    model_id = "null"
    dimensions = 0

    def is_available(self) -> bool:
        return False

    def embed_text(self, text: str, context_hint: str | None = None) -> EmbeddingVector:
        del text, context_hint
        raise EmbeddingUnavailable("embedding adapter is unavailable")

    def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]:
        return [self.embed_text(text) for text in texts]

    def similarity(self, a: EmbeddingVector, b: EmbeddingVector) -> float:
        return cosine(a, b)

    def top_k_similar(
        self, query: EmbeddingVector, corpus: list[EmbeddingVector], k: int
    ) -> list[tuple[int, float]]:
        scored = [
            (index, self.similarity(query, vector))
            for index, vector in enumerate(corpus)
        ]
        return sorted(scored, key=lambda item: item[1], reverse=True)[:k]
