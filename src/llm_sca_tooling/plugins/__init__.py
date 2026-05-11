"""Interface plugin system for llm-sca-tooling extension points."""

from llm_sca_tooling.plugins.base import InterfacePluginBase, TraversalDirection
from llm_sca_tooling.plugins.interface_record import (
    InterfaceKind,
    InterfaceOperation,
    InterfaceRecord,
)
from llm_sca_tooling.plugins.registry import (
    NoOpPlugin,
    Plugin,
    PluginCapabilities,
    PluginRegistry,
    build_default_registry,
)

__all__ = [
    "InterfaceKind",
    "InterfaceOperation",
    "InterfacePluginBase",
    "InterfaceRecord",
    "NoOpPlugin",
    "Plugin",
    "PluginCapabilities",
    "PluginRegistry",
    "TraversalDirection",
    "build_default_registry",
]
