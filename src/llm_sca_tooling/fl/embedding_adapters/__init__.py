"""Embedding adapter implementations."""

from llm_sca_tooling.fl.embedding_adapters.null_adapter import NullEmbeddingAdapter
from llm_sca_tooling.fl.embedding_adapters.sampling_adapter import (
    SamplingEmbeddingAdapter,
)

__all__ = ["NullEmbeddingAdapter", "SamplingEmbeddingAdapter"]
