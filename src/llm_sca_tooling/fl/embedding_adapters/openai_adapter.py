"""Placeholder for a future remote embedding adapter.

Phase 9 activates the embedding boundary but keeps network-dependent adapters
out of the default path. This class is intentionally unavailable until a later
phase adds governed network configuration.
"""

from __future__ import annotations

from llm_sca_tooling.fl.embedding_interface import (
    EmbeddingInterface,
    EmbeddingUnavailable,
    EmbeddingVector,
)


class OpenAIEmbeddingAdapter(EmbeddingInterface):
    def __init__(self, model_id: str = "text-embedding-3-small") -> None:
        self.model_id = model_id
        self.dimensions = 1536

    def is_available(self) -> bool:
        return False

    def embed_text(self, text: str, context_hint: str | None = None) -> EmbeddingVector:
        _ = (text, context_hint)
        raise EmbeddingUnavailable("remote embedding adapter is not configured")
