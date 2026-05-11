"""Optional network embedding adapter placeholder."""

from llm_sca_tooling.fl.embedding_adapters.null_adapter import NullEmbeddingAdapter

OpenAIEmbeddingAdapter = NullEmbeddingAdapter

__all__ = ["OpenAIEmbeddingAdapter"]
