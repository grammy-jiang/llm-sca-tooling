"""Interface plugin registry."""

from __future__ import annotations

from dataclasses import dataclass, field

from llm_sca_tooling.plugins.base import InterfacePluginBase
from llm_sca_tooling.plugins.capability import (
    PluginAvailability,
    PluginCapabilityDescriptor,
)
from llm_sca_tooling.plugins.interface_record import InterfaceKind
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = [
    "NoOpPlugin",
    "Plugin",
    "PluginCapabilities",
    "PluginRegistry",
    "build_default_registry",
]

logger = get_logger(__name__)


@dataclass
class PluginCapabilities:
    detect: bool = False
    index: bool = False
    link: bool = False
    traverse: bool = False


@dataclass
class Plugin(InterfacePluginBase):
    plugin_id: str
    name: str
    version: str
    capabilities: PluginCapabilities = field(default_factory=PluginCapabilities)
    plugin_version: str = field(init=False)

    def __post_init__(self) -> None:
        self.plugin_version = self.version

    async def check_availability(self) -> PluginAvailability:
        return PluginAvailability(plugin_id=self.plugin_id, available=True)

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.version,
            interface_kinds=[InterfaceKind.custom],
            max_confidence="heuristic",
        )

    async def detect(self, repo, snapshot, file_list):  # type: ignore[no-untyped-def]
        from llm_sca_tooling.plugins.base import PluginDetectResult

        return PluginDetectResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
        )

    async def index(self, repo, snapshot, detect_result, config):  # type: ignore[no-untyped-def]
        from llm_sca_tooling.plugins.base import PluginIndexResult

        return PluginIndexResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
        )

    async def link(self, repo, snapshot, index_result, workspace, config):  # type: ignore[no-untyped-def]
        from llm_sca_tooling.plugins.base import PluginLinkResult

        return PluginLinkResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
        )

    async def traverse(self, node_id, direction, workspace):  # type: ignore[no-untyped-def]
        return []


class NoOpPlugin(Plugin):
    """Built-in no-op plugin used by legacy registry tests."""

    def __init__(self) -> None:
        super().__init__(
            plugin_id="noop",
            name="No-Op Plugin",
            version="0.1.0",
            capabilities=PluginCapabilities(),
        )

    async def check_availability(self) -> PluginAvailability:
        return PluginAvailability(
            plugin_id=self.plugin_id,
            available=False,
            missing_deps=["not_yet_implemented"],
        )


class PluginRegistry:
    """Register, load, and list interface plugins."""

    def __init__(self, *, include_noop: bool = True) -> None:
        self._plugins: dict[str, InterfacePluginBase] = {}
        if include_noop:
            self.register(NoOpPlugin())

    def register(self, plugin: InterfacePluginBase) -> None:
        if plugin.plugin_id in self._plugins:
            raise ValueError(f"duplicate plugin_id: {plugin.plugin_id}")
        self._plugins[plugin.plugin_id] = plugin
        logger.debug(
            "Registered plugin %r (%s)", plugin.plugin_id, plugin.plugin_version
        )

    def unregister(self, plugin_id: str) -> None:
        self._plugins.pop(plugin_id, None)

    def get(self, plugin_id: str) -> InterfacePluginBase | None:
        return self._plugins.get(plugin_id)

    def load(self, plugin_id: str) -> InterfacePluginBase | None:
        return self.get(plugin_id)

    def all_plugins(self) -> list[InterfacePluginBase]:
        return list(self._plugins.values())

    def list_plugins(self) -> list[InterfacePluginBase]:
        return self.all_plugins()

    async def available_plugins(self) -> list[InterfacePluginBase]:
        available: list[InterfacePluginBase] = []
        for plugin in self._plugins.values():
            if (await plugin.check_availability()).available:
                available.append(plugin)
        return available

    def capability_report(self) -> list[PluginCapabilityDescriptor]:
        return [plugin.describe_capability() for plugin in self._plugins.values()]

    async def availability_report(self) -> list[PluginAvailability]:
        return [await plugin.check_availability() for plugin in self._plugins.values()]

    def reload(self, plugin_id: str | None = None) -> None:
        target = plugin_id or "all"
        logger.info("Plugin reload requested for %r", target)


def build_default_registry() -> PluginRegistry:
    from llm_sca_tooling.plugins.backlog import backlog_plugins
    from llm_sca_tooling.plugins.http_rest.plugin import HttpRestPlugin
    from llm_sca_tooling.plugins.omniorb_idl.plugin import OmniOrbIdlPlugin
    from llm_sca_tooling.plugins.websocket.plugin import WebSocketPlugin

    registry = PluginRegistry(include_noop=False)
    for plugin in [
        HttpRestPlugin(),
        WebSocketPlugin(),
        OmniOrbIdlPlugin(),
        *backlog_plugins(),
    ]:
        registry.register(plugin)
    return registry
