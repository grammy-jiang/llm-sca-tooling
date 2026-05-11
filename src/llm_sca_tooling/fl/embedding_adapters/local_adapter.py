"""Optional local embedding adapter placeholder.

Phase 9 activates the interface; deployments may replace this with a fastembed
adapter without changing the retrieval contract.
"""

from llm_sca_tooling.fl.embedding_adapters.null_adapter import NullEmbeddingAdapter

LocalEmbeddingAdapter = NullEmbeddingAdapter

__all__ = ["LocalEmbeddingAdapter"]
