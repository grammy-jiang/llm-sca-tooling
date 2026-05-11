"""Embedding interface for Phase 9 semantic retrieval."""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from typing import Protocol

from llm_sca_tooling.fl.models import StrictFlModel

__all__ = [
    "EmbeddingInterface",
    "EmbeddingUnavailable",
    "EmbeddingVector",
    "make_vector",
]


class EmbeddingUnavailable(RuntimeError):  # noqa: N818
    pass


class EmbeddingVector(StrictFlModel):
    vector: list[float]
    model_id: str
    dimensions: int
    text_hash: str
    produced_ts: str


class EmbeddingInterface(Protocol):
    model_id: str
    dimensions: int

    def is_available(self) -> bool: ...
    def embed_text(
        self, text: str, context_hint: str | None = None
    ) -> EmbeddingVector: ...
    def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]: ...

    def similarity(self, a: EmbeddingVector, b: EmbeddingVector) -> float: ...

    def top_k_similar(
        self, query: EmbeddingVector, corpus: list[EmbeddingVector], k: int
    ) -> list[tuple[int, float]]: ...


def make_vector(text_value: str, vector: list[float], model_id: str) -> EmbeddingVector:
    return EmbeddingVector(
        vector=vector,
        model_id=model_id,
        dimensions=len(vector),
        text_hash=hashlib.sha256(text_value.encode()).hexdigest(),
        produced_ts=datetime.now(UTC).isoformat(),
    )


def cosine(a: EmbeddingVector, b: EmbeddingVector) -> float:
    dot = sum(left * right for left, right in zip(a.vector, b.vector, strict=False))
    left_norm = math.sqrt(sum(value * value for value in a.vector))
    right_norm = math.sqrt(sum(value * value for value in b.vector))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
