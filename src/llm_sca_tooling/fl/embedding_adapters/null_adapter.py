"""Null embedding adapter used by default and in CI."""

from __future__ import annotations

from llm_sca_tooling.fl.embedding_interface import (
    EmbeddingInterface,
    EmbeddingUnavailable,
    EmbeddingVector,
)


class NullEmbeddingAdapter(EmbeddingInterface):
    def __init__(self, model_id: str = "null", dimensions: int = 1) -> None:
        self.model_id = model_id
        self.dimensions = dimensions

    def is_available(self) -> bool:
        return False

    def embed_text(self, text: str, context_hint: str | None = None) -> EmbeddingVector:
        _ = (text, context_hint)
        raise EmbeddingUnavailable("embedding adapter is disabled")

    def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]:
        _ = texts
        raise EmbeddingUnavailable("embedding adapter is disabled")
