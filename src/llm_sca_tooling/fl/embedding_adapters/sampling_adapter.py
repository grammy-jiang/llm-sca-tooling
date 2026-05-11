"""MCP-Sampling-backed embedding adapter."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

from llm_sca_tooling.fl.embedding_interface import (
    EmbeddingInterface,
    EmbeddingUnavailable,
    EmbeddingVector,
)


class SamplingEmbeddingAdapter(EmbeddingInterface):
    """Uses MCP Sampling to generate text embeddings when a real model is unavailable.

    Falls back to :class:`~llm_sca_tooling.fl.embedding_adapters.null_adapter.NullEmbeddingAdapter`
    behaviour (raising :exc:`EmbeddingUnavailable`) when the sampling client is
    not set or not available.
    """

    def __init__(self, sampling_client: Any, *, dimensions: int = 256) -> None:
        self._client = sampling_client
        self.model_id = "llm-sampling-embedding"
        self.dimensions = dimensions

    def is_available(self) -> bool:
        return self._client is not None and bool(
            getattr(self._client, "available", False)
        )

    def embed_text(self, text: str, context_hint: str | None = None) -> EmbeddingVector:
        if not self.is_available():
            raise EmbeddingUnavailable("SamplingEmbeddingAdapter: client unavailable")
        prompt = (
            f"Produce a JSON array of exactly {self.dimensions} floats that represents "
            f"a semantic embedding for the following text. "
            f"Output ONLY the JSON array, no explanation.\n\nText: {text[:500]}"
        )
        try:
            response = self._client.create_message(
                prompt=prompt, max_tokens=self.dimensions * 12
            )
            content = str(response.get("content", "")).strip()
            vector = _parse_vector(content, self.dimensions)
            vector = _normalize(vector)
            import hashlib

            text_hash = hashlib.sha256(text.encode()).hexdigest()
            return EmbeddingVector(
                vector=vector,
                model_id=self.model_id,
                dimensions=self.dimensions,
                text_hash=text_hash,
                produced_ts=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )
        except Exception as exc:
            raise EmbeddingUnavailable(
                f"SamplingEmbeddingAdapter: failed to produce embedding: {exc}"
            ) from exc

    def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]:
        return [self.embed_text(text) for text in texts]


def _parse_vector(content: str, dimensions: int) -> list[float]:
    """Extract a float list from LLM response; pad or trim to ``dimensions``."""
    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end != -1:
        try:
            parsed = json.loads(content[start : end + 1])
            if isinstance(parsed, list):
                floats = [float(v) for v in parsed]
                if len(floats) >= dimensions:
                    return floats[:dimensions]
                # Pad with zeros if too short
                return floats + [0.0] * (dimensions - len(floats))
        except (json.JSONDecodeError, ValueError):
            pass
    # Fallback: generate a deterministic pseudo-vector from content hash
    import hashlib

    digest = hashlib.sha256(content.encode()).digest()
    values: list[float] = []
    for i in range(dimensions):
        byte = digest[i % len(digest)]
        values.append((byte / 127.5) - 1.0)
    return values


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return vector
    return [v / norm for v in vector]


__all__ = ["SamplingEmbeddingAdapter"]
