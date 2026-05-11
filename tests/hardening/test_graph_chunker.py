"""Tests for GraphChunker."""

from __future__ import annotations

from llm_sca_tooling.hardening.graph_chunker import GraphChunker


def _node_ids(n: int) -> list[str]:
    return [f"module.pkg.fn{i}" for i in range(n)]


def test_chunk_splits_large_graph() -> None:
    chunker = GraphChunker(max_chunk_nodes=5)
    nodes = _node_ids(12)
    manifest = chunker.chunk("repo1", "abc12345", nodes)
    assert manifest.chunk_count >= 3


def test_chunk_no_split_for_small_graph() -> None:
    chunker = GraphChunker(max_chunk_nodes=100)
    nodes = _node_ids(10)
    manifest = chunker.chunk("repo1", "abc12345", nodes)
    assert manifest.chunk_count == 1


def test_each_chunk_fits_max_size() -> None:
    chunker = GraphChunker(max_chunk_nodes=7)
    nodes = _node_ids(20)
    manifest = chunker.chunk("repo1", "abc12345", nodes)
    for chunk in manifest.chunks:
        assert len(chunk.nodes) <= 7


def test_chunk_total_nodes_preserved() -> None:
    chunker = GraphChunker(max_chunk_nodes=4)
    nodes = _node_ids(11)
    manifest = chunker.chunk("repo1", "abc12345", nodes)
    assert manifest.total_nodes == 11


def test_chunk_ids_are_unique() -> None:
    chunker = GraphChunker(max_chunk_nodes=3)
    nodes = _node_ids(9)
    manifest = chunker.chunk("repo1", "abc12345", nodes)
    ids = [c.chunk_id for c in manifest.chunks]
    assert len(ids) == len(set(ids))


def test_get_chunk_by_id() -> None:
    chunker = GraphChunker(max_chunk_nodes=5)
    nodes = _node_ids(10)
    manifest = chunker.chunk("repo1", "abc12345", nodes)
    first_id = manifest.chunks[0].chunk_id
    chunk = chunker.get_chunk(first_id)
    assert chunk is not None
    assert chunk.chunk_id == first_id
