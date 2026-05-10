from __future__ import annotations

import pytest

from llm_sca_tooling.fl.embedding_adapters.null_adapter import NullEmbeddingAdapter
from llm_sca_tooling.fl.embedding_interface import EmbeddingUnavailable, vector_for_text
from llm_sca_tooling.fl.vector_cache import VectorCache


def test_null_adapter_is_unavailable() -> None:
    adapter = NullEmbeddingAdapter()

    assert not adapter.is_available()
    with pytest.raises(EmbeddingUnavailable):
        adapter.embed_text("hello")


def test_similarity_and_top_k_ordering() -> None:
    adapter = NullEmbeddingAdapter(dimensions=2)
    query = vector_for_text("q", vector=[1.0, 0.0], model_id="test")
    corpus = [
        vector_for_text("a", vector=[0.0, 1.0], model_id="test"),
        vector_for_text("b", vector=[1.0, 0.0], model_id="test"),
    ]

    assert adapter.top_k_similar(query, corpus, 2) == [(1, 1.0), (0, 0.0)]


def test_vector_cache_store_get_and_invalidate(fl_workspace, fl_repo) -> None:
    cache = VectorCache(fl_workspace.conn)
    vector = vector_for_text("validate", vector=[1.0, 0.0], model_id="test")

    cache.store("node:method:validate", "test", "sha1", vector)

    assert cache.get("node:method:validate", "test", "sha1") == vector
    assert cache.get("node:method:validate", "test", "sha2") is None
    assert cache.invalidate_file("src/pkg/core.py", fl_repo.repo_id, "sha2") == 1
    assert cache.get("node:method:validate", "test", "sha1") is None
