"""Local fastembed adapter, loaded lazily so CI can run without the model."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from llm_sca_tooling.fl.embedding_interface import (
    EmbeddingInterface,
    EmbeddingUnavailable,
    EmbeddingVector,
    text_hash,
)
from llm_sca_tooling.storage.workspace import _now_ts


class LocalFastEmbedAdapter(EmbeddingInterface):
    def __init__(self, model_id: str = "BAAI/bge-small-en-v1.5") -> None:
        self.model_id = model_id
        self.dimensions = 384
        self._model: Any | None = None

    def is_available(self) -> bool:
        try:
            import fastembed  # noqa: F401
        except Exception:
            return False
        return True

    def embed_text(self, text: str, context_hint: str | None = None) -> EmbeddingVector:
        _ = context_hint
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]:
        model = self._load_model()
        vectors = cast(Iterable[Iterable[float]], model.embed(texts))
        results: list[EmbeddingVector] = []
        for text, vector in zip(texts, vectors, strict=True):
            values = [float(item) for item in vector]
            self.dimensions = len(values)
            results.append(
                EmbeddingVector(
                    vector=values,
                    model_id=self.model_id,
                    dimensions=len(values),
                    text_hash=text_hash(text),
                    produced_ts=_now_ts(),
                )
            )
        return results

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from fastembed import TextEmbedding
        except Exception as exc:
            raise EmbeddingUnavailable("fastembed is not installed") from exc
        self._model = TextEmbedding(model_name=self.model_id)
        return self._model
