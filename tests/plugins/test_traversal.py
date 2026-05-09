"""Tests for CrossLanguageTraverser."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from llm_sca_tooling.plugins.registry import PluginRegistry
from llm_sca_tooling.plugins.traversal import (
    CrossLanguageTraversalResult,
    CrossLanguageTraverser,
)


@pytest.fixture
def empty_registry() -> PluginRegistry:
    """Registry with no available plugins (NoOpPlugin is unavailable)."""
    registry = PluginRegistry()
    return registry


@pytest.fixture
def graph_store() -> MagicMock:
    return MagicMock()


def test_traverser_initializes(
    empty_registry: PluginRegistry, graph_store: MagicMock
) -> None:
    traverser = CrossLanguageTraverser(empty_registry, graph_store)
    assert traverser.plugin_registry is empty_registry
    assert traverser.graph_store is graph_store


def test_traverse_with_max_hops_zero_terminates_early(
    empty_registry: PluginRegistry, graph_store: MagicMock
) -> None:
    traverser = CrossLanguageTraverser(empty_registry, graph_store)
    result = traverser.traverse("node:start", max_hops=0)

    assert isinstance(result, CrossLanguageTraversalResult)
    assert result.terminated_early is True
    assert result.termination_reason == "max_hops"
    assert result.start_node_id == "node:start"


def test_traverse_no_plugins_returns_empty_hops(graph_store: MagicMock) -> None:
    registry = PluginRegistry([])  # truly empty
    traverser = CrossLanguageTraverser(registry, graph_store)
    result = traverser.traverse("node:start")

    assert result.hops == []
    assert result.termination_reason in ("no_plugins", "no_more_links")


def test_traverse_no_available_plugins_returns_no_hops(graph_store: MagicMock) -> None:
    registry = PluginRegistry()  # NoOpPlugin — unavailable
    traverser = CrossLanguageTraverser(registry, graph_store)
    result = traverser.traverse("node:start")

    assert result.start_node_id == "node:start"
    assert result.total_hops == 0


def test_traverse_returns_start_node_in_reached(graph_store: MagicMock) -> None:
    registry = PluginRegistry()
    traverser = CrossLanguageTraverser(registry, graph_store)
    result = traverser.traverse("node:xyz")

    assert "node:xyz" in result.reached_node_ids
