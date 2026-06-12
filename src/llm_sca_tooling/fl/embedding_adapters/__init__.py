"""Embedding adapters."""

from llm_sca_tooling.fl.embedding_adapters.fastembed_adapter import (
    FastembedEmbeddingAdapter,
)
from llm_sca_tooling.fl.embedding_adapters.null_adapter import NullEmbeddingAdapter
from llm_sca_tooling.fl.embedding_interface import EmbeddingInterface

__all__ = [
    "FastembedEmbeddingAdapter",
    "NullEmbeddingAdapter",
    "get_default_embedding_adapter",
]


def get_default_embedding_adapter() -> EmbeddingInterface:
    """Return the best available embedding adapter.

    Fastembed when the optional dependency is installed, otherwise the null
    adapter — retrieval degrades to keyword + graph signals, never breaks.
    """
    adapter = FastembedEmbeddingAdapter()
    if adapter.is_available():
        return adapter
    return NullEmbeddingAdapter()
