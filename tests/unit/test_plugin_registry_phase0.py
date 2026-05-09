from __future__ import annotations

from llm_sca_tooling.plugins.registry import NoOpPlugin, PluginRegistry


def test_default_registry_loads_noop_plugin() -> None:
    registry = PluginRegistry()
    plugin = registry.load("noop")
    assert isinstance(plugin, NoOpPlugin)
    assert registry.list_plugins()
