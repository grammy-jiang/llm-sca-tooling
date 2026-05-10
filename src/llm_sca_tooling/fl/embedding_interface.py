"""Embedding abstraction for Phase 9 fault localisation."""

from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import StrictBaseModel


class EmbeddingUnavailableError(RuntimeError):
    """Raised when an embedding adapter is configured but unavailable."""


EmbeddingUnavailable = EmbeddingUnavailableError


class EmbeddingVector(StrictBaseModel):
    vector: list[float]
    model_id: str = Field(min_length=1)
    dimensions: int = Field(ge=1)
    text_hash: str = Field(min_length=1)
    produced_ts: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dimensions(self) -> EmbeddingVector:
        if len(self.vector) != self.dimensions:
            raise ValueError("vector length must match dimensions")
        return self


class EmbeddingConfig(StrictBaseModel):
    model_id: str = "BAAI/bge-small-en-v1.5"
    adapter: str = "null"
    dimensions: int = Field(default=384, ge=1)
    batch_size: int = Field(default=32, ge=1)
    timeout_seconds: float = Field(default=10.0, gt=0.0)
    max_symbols_to_embed: int = Field(default=10000, ge=1)
    similarity_threshold: float = Field(default=0.35, ge=-1.0, le=1.0)


class EmbeddingInterface(ABC):
    model_id: str
    dimensions: int

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when the adapter can embed without extra setup."""

    @abstractmethod
    def embed_text(self, text: str, context_hint: str | None = None) -> EmbeddingVector:
        """Embed one text item."""

    def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]:
        return [self.embed_text(text) for text in texts]

    def similarity(self, a: EmbeddingVector, b: EmbeddingVector) -> float:
        if a.dimensions != b.dimensions:
            raise ValueError("embedding dimensions do not match")
        dot = sum(left * right for left, right in zip(a.vector, b.vector, strict=True))
        norm_a = math.sqrt(sum(value * value for value in a.vector))
        norm_b = math.sqrt(sum(value * value for value in b.vector))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm_a * norm_b)))

    def top_k_similar(
        self,
        query: EmbeddingVector,
        corpus: list[EmbeddingVector],
        k: int,
    ) -> list[tuple[int, float]]:
        scored = [
            (index, self.similarity(query, candidate))
            for index, candidate in enumerate(corpus)
        ]
        return sorted(scored, key=lambda item: item[1], reverse=True)[:k]


def vector_for_text(
    text: str,
    *,
    vector: list[float],
    model_id: str,
) -> EmbeddingVector:
    return EmbeddingVector(
        vector=vector,
        model_id=model_id,
        dimensions=len(vector),
        text_hash=text_hash(text),
        produced_ts=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
