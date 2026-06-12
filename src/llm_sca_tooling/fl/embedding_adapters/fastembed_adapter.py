"""Fastembed-backed local embedding adapter (Phase 9 activation).

`fastembed` is an optional dependency (`pip install llm-sca-tooling[embeddings]`).
When the library is missing the adapter reports `is_available() == False` and
callers fall back to the null adapter — missing backends degrade to partial
evidence, they never break retrieval.

The encoder is injectable so unit tests can exercise the full adapter contract
without the optional dependency or model downloads.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from functools import cache

from llm_sca_tooling.fl.embedding_interface import (
    EmbeddingUnavailable,
    EmbeddingVector,
    cosine,
    make_vector,
)

__all__ = ["DEFAULT_MODEL_ID", "FastembedEmbeddingAdapter"]

DEFAULT_MODEL_ID = "BAAI/bge-small-en-v1.5"

Encoder = Callable[[list[str]], list[list[float]]]


def _fastembed_installed() -> bool:
    return importlib.util.find_spec("fastembed") is not None


@cache
def _fastembed_encoder(model_id: str) -> Encoder:
    """Build a fastembed encoder (loads/downloads the model on first use)."""
    from fastembed import TextEmbedding  # noqa: PLC0415

    model = TextEmbedding(model_name=model_id)

    def encode(texts: list[str]) -> list[list[float]]:
        return [[float(value) for value in vector] for vector in model.embed(texts)]

    return encode


class FastembedEmbeddingAdapter:
    """Local semantic embedding adapter satisfying ``EmbeddingInterface``.

    Availability is a cheap import check; the underlying model is loaded
    lazily on the first embed call and cached process-wide.
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        *,
        encoder: Encoder | None = None,
    ) -> None:
        self.model_id = model_id
        self._encoder = encoder
        self.dimensions = 0

    def is_available(self) -> bool:
        return self._encoder is not None or _fastembed_installed()

    def _resolve_encoder(self) -> Encoder:
        if self._encoder is None:
            if not _fastembed_installed():
                raise EmbeddingUnavailable(
                    "fastembed is not installed; "
                    "install the 'embeddings' extra to enable semantic retrieval"
                )
            self._encoder = _fastembed_encoder(self.model_id)
        return self._encoder

    def embed_text(self, text: str, context_hint: str | None = None) -> EmbeddingVector:
        del context_hint
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]:
        raw_vectors = self._resolve_encoder()(texts)
        vectors = [
            make_vector(text, vector, self.model_id)
            for text, vector in zip(texts, raw_vectors, strict=True)
        ]
        if vectors:
            self.dimensions = vectors[0].dimensions
        return vectors

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
