"""Interface plugin registry."""

from __future__ import annotations

from collections import OrderedDict

from llm_sca_tooling.plugins.base import InterfacePluginBase
from llm_sca_tooling.plugins.capability import PluginAvailability, PluginCapabilityDescriptor
from llm_sca_tooling.plugins.errors import DuplicatePluginError, PluginNotFoundError


class PluginRegistry:
    def __init__(self, plugins: list[InterfacePluginBase] | None = None) -> None:
        self._plugins: OrderedDict[str, InterfacePluginBase] = OrderedDict()
        for plugin in plugins or []:
            self.register(plugin)

    def register(self, plugin: InterfacePluginBase) -> None:
        if plugin.plugin_id in self._plugins:
            raise DuplicatePluginError(f"duplicate plugin_id: {plugin.plugin_id}")
        self._plugins[plugin.plugin_id] = plugin

    def unregister(self, plugin_id: str) -> None:
        if plugin_id not in self._plugins:
            raise PluginNotFoundError(f"plugin not found: {plugin_id}")
        del self._plugins[plugin_id]

    def get(self, plugin_id: str) -> InterfacePluginBase | None:
        return self._plugins.get(plugin_id)

    def require(self, plugin_id: str) -> InterfacePluginBase:
        plugin = self.get(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(f"plugin not found: {plugin_id}")
        return plugin

    def available_plugins(self) -> list[InterfacePluginBase]:
        return [plugin for plugin in self._plugins.values() if plugin.check_availability().available]

    def all_plugins(self) -> list[InterfacePluginBase]:
        return list(self._plugins.values())

    def capability_report(self) -> list[PluginCapabilityDescriptor]:
        return [plugin.describe_capability() for plugin in self._plugins.values()]

    def availability_report(self) -> list[PluginAvailability]:
        return [plugin.check_availability() for plugin in self._plugins.values()]


def default_plugin_registry() -> PluginRegistry:
    from llm_sca_tooling.plugins.backlog import DbusStub, GrpcStub, MqttStub, ProtobufStub, ZeroMQStub
    from llm_sca_tooling.plugins.http_rest import HttpRestPlugin
    from llm_sca_tooling.plugins.omniorb_idl import OmniOrbIdlPlugin
    from llm_sca_tooling.plugins.websocket import WebSocketPlugin

    return PluginRegistry(
        [
            HttpRestPlugin(),
            WebSocketPlugin(),
            OmniOrbIdlPlugin(),
            GrpcStub(),
            ProtobufStub(),
            ZeroMQStub(),
            MqttStub(),
            DbusStub(),
        ]
    )
