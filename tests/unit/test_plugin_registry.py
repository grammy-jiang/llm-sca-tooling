"""Tests for the plugin registry."""

from __future__ import annotations

import pytest

from llm_sca_tooling.plugins.registry import (
    NoOpPlugin,
    Plugin,
    PluginRegistry,
)


@pytest.fixture()
def registry() -> PluginRegistry:
    return PluginRegistry()


def test_noop_plugin_loadable(registry: PluginRegistry) -> None:
    plugin = registry.load("noop")
    assert isinstance(plugin, NoOpPlugin)


def test_list_plugins_nonempty(registry: PluginRegistry) -> None:
    plugins = registry.list_plugins()
    assert len(plugins) >= 1


def test_register_and_load_custom_plugin(registry: PluginRegistry) -> None:
    p = Plugin(plugin_id="my-plugin", name="My Plugin", version="1.0.0")
    registry.register(p)
    loaded = registry.load("my-plugin")
    assert loaded is p


def test_load_unknown_returns_none(registry: PluginRegistry) -> None:
    assert registry.load("nonexistent") is None


def test_registry_is_separate_per_instance() -> None:
    r1, r2 = PluginRegistry(), PluginRegistry()
    r1.register(Plugin(plugin_id="r1-only", name="R1", version="1.0"))
    assert r2.load("r1-only") is None


def test_reload_is_noop(registry: PluginRegistry) -> None:
    registry.reload()
    registry.reload("noop")


def test_noop_plugin_has_no_capabilities() -> None:
    p = NoOpPlugin()
    assert p.capabilities.detect is False
    assert p.capabilities.index is False
