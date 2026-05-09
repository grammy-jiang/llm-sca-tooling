"""Tests for GraphSliceGenerator."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.indexing.graph_slices import GraphSliceGenerator
from llm_sca_tooling.storage import initialize_workspace


@pytest.fixture
def workspace(tmp_path: Path):
    store = initialize_workspace(tmp_path / ".llm-sca")
    yield store
    store.close()


def test_graph_slice_generator_initializes(workspace) -> None:
    gen = GraphSliceGenerator(workspace)
    assert gen.workspace is workspace


def test_by_file_returns_empty_slice_for_unknown_file(workspace) -> None:
    gen = GraphSliceGenerator(workspace)
    result = gen.by_file("repo:unknown", "src/nonexistent.py")
    assert result.nodes == []
    assert result.edges == []


def test_by_symbol_returns_empty_slice_for_unknown_symbol(workspace) -> None:
    gen = GraphSliceGenerator(workspace)
    result = gen.by_symbol("repo:unknown", "my.module.NonExistent")
    assert result.nodes == []
    assert result.edges == []


def test_by_symbol_with_node_id_prefix_returns_empty_when_missing(workspace) -> None:
    gen = GraphSliceGenerator(workspace)
    result = gen.by_symbol("repo:unknown", "node:does-not-exist")
    assert result.nodes == []
