"""Interface plugin registry."""

from __future__ import annotations

from collections import OrderedDict

from llm_sca_tooling.indexing.backends.base import BackendRunStats
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.plugins.base import (
    InterfacePluginBase,
    PluginConfig,
    PluginDetectResult,
    PluginIndexResult,
    PluginLinkResult,
    TraversalLink,
)
from llm_sca_tooling.plugins.capability import (
    ConfidenceLevel,
    InterfaceKind,
    PluginAvailability,
    PluginCapabilityDescriptor,
    TraversalDirection,
)
from llm_sca_tooling.plugins.errors import DuplicatePluginError, PluginNotFoundError
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.graph_store import GraphStore


class NoOpPlugin(InterfacePluginBase):
    plugin_id = "noop"
    plugin_version = "0.1.0"
    interface_kind = InterfaceKind.CUSTOM

    def check_availability(self) -> PluginAvailability:
        return PluginAvailability(plugin_id=self.plugin_id, available=True)

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            interface_kinds=[self.interface_kind],
            max_confidence=ConfidenceLevel.HEURISTIC,
        )

    def detect(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        file_list: list[ScannedFile],
        config: PluginConfig,
    ) -> PluginDetectResult:
        return PluginDetectResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=_snapshot_id(snapshot),
            run_stats=BackendRunStats(files_scanned=len(file_list)),
        )

    def index(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        detect_result: PluginDetectResult,
        config: PluginConfig,
    ) -> PluginIndexResult:
        return PluginIndexResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=detect_result.snapshot_id,
        )

    def link(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        index_result: PluginIndexResult,
        graph_store: GraphStore,
        config: PluginConfig,
    ) -> PluginLinkResult:
        return PluginLinkResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=index_result.snapshot_id,
        )

    def traverse(
        self, node_id: str, direction: TraversalDirection, graph_store: GraphStore
    ) -> list[TraversalLink]:
        return []


class PluginRegistry:
    def __init__(self, plugins: list[InterfacePluginBase] | None = None) -> None:
        self._plugins: OrderedDict[str, InterfacePluginBase] = OrderedDict()
        initial_plugins = [NoOpPlugin()] if plugins is None else plugins
        for plugin in initial_plugins:
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

    def load(self, plugin_id: str) -> InterfacePluginBase | None:
        return self.get(plugin_id)

    def require(self, plugin_id: str) -> InterfacePluginBase:
        plugin = self.get(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(f"plugin not found: {plugin_id}")
        return plugin

    def available_plugins(self) -> list[InterfacePluginBase]:
        return [
            plugin
            for plugin in self._plugins.values()
            if plugin.check_availability().available
        ]

    def all_plugins(self) -> list[InterfacePluginBase]:
        return list(self._plugins.values())

    def list_plugins(self) -> list[InterfacePluginBase]:
        return self.all_plugins()

    def reload(self, plugin_id: str | None = None) -> None:
        if plugin_id is not None:
            self.require(plugin_id)

    def capability_report(self) -> list[PluginCapabilityDescriptor]:
        return [plugin.describe_capability() for plugin in self._plugins.values()]

    def availability_report(self) -> list[PluginAvailability]:
        return [plugin.check_availability() for plugin in self._plugins.values()]


def default_plugin_registry() -> PluginRegistry:
    from llm_sca_tooling.plugins.backlog import (
        DbusStub,
        GrpcStub,
        MqttStub,
        ProtobufStub,
        ZeroMQStub,
    )
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


def _snapshot_id(snapshot: SnapshotRef) -> str:
    return snapshot.worktree_snapshot_id or snapshot.git_sha or snapshot.captured_ts
