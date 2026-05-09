"""Cross-language interface plugin system."""

from llm_sca_tooling.plugins.registry import (
    NoOpPlugin,
    PluginRegistry,
    default_plugin_registry,
)

__all__ = ["NoOpPlugin", "PluginRegistry", "default_plugin_registry"]
