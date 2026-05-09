"""Plugin system exceptions."""

from __future__ import annotations


class PluginError(Exception):
    """Base plugin system error."""


class DuplicatePluginError(PluginError):
    """A plugin ID was registered more than once."""


class PluginNotFoundError(PluginError):
    """Requested plugin does not exist."""


class InterfaceNotFoundError(PluginError):
    """Requested interface record does not exist."""
