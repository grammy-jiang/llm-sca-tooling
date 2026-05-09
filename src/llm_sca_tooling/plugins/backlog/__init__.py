"""Backlog plugin stubs for future interface families."""

from __future__ import annotations

from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.plugins.base import InterfacePluginBase, PluginConfig, PluginDetectResult, PluginIndexResult, PluginLinkResult, TraversalLink
from llm_sca_tooling.plugins.capability import ConfidenceLevel, InterfaceKind, PluginAvailability, PluginCapabilityDescriptor, TraversalDirection
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.graph_store import GraphStore


class _BacklogStub(InterfacePluginBase):
    plugin_id = "backlog"
    plugin_version = "0.1.0"
    interface_kind = InterfaceKind.CUSTOM
    server_languages: list[str] = []
    client_languages: list[str] = []
    node_types: list[GraphNodeType] = []
    edge_types: list[GraphEdgeType] = []

    def check_availability(self) -> PluginAvailability:
        return PluginAvailability(plugin_id=self.plugin_id, available=False, missing_deps=["not_yet_implemented"], warnings=["not_yet_implemented"])

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(plugin_id=self.plugin_id, plugin_version=self.plugin_version, interface_kinds=[self.interface_kind], supported_server_languages=self.server_languages, supported_client_languages=self.client_languages, emitted_node_types=self.node_types, emitted_edge_types=self.edge_types, max_confidence=ConfidenceLevel.ANALYSER)

    def detect(self, repo: RepoRef, snapshot: SnapshotRef, file_list: list[ScannedFile], config: PluginConfig) -> PluginDetectResult:
        raise NotImplementedError("backlog plugin is not implemented")

    def index(self, repo: RepoRef, snapshot: SnapshotRef, detect_result: PluginDetectResult, config: PluginConfig) -> PluginIndexResult:
        raise NotImplementedError("backlog plugin is not implemented")

    def link(self, repo: RepoRef, snapshot: SnapshotRef, index_result: PluginIndexResult, graph_store: GraphStore, config: PluginConfig) -> PluginLinkResult:
        raise NotImplementedError("backlog plugin is not implemented")

    def traverse(self, node_id: str, direction: TraversalDirection, graph_store: GraphStore) -> list[TraversalLink]:
        raise NotImplementedError("backlog plugin is not implemented")


class GrpcStub(_BacklogStub):
    plugin_id = "grpc"
    interface_kind = InterfaceKind.GRPC
    server_languages = ["python", "cpp", "go"]
    client_languages = ["python", "typescript"]
    node_types = [GraphNodeType.GRPC_SERVICE]
    edge_types = [GraphEdgeType.EXPOSES, GraphEdgeType.CONSUMES]


class ProtobufStub(_BacklogStub):
    plugin_id = "protobuf"
    interface_kind = InterfaceKind.PROTOBUF
    server_languages = ["python", "cpp", "go", "typescript"]
    client_languages = ["python", "cpp", "go", "typescript"]
    node_types = [GraphNodeType.PROTOBUF_MESSAGE]
    edge_types = [GraphEdgeType.DATAFLOW]


class ZeroMQStub(_BacklogStub):
    plugin_id = "zeromq"
    interface_kind = InterfaceKind.ZEROMQ
    server_languages = ["python", "cpp"]
    client_languages = ["python", "typescript"]
    edge_types = [GraphEdgeType.FFI]


class MqttStub(_BacklogStub):
    plugin_id = "mqtt"
    interface_kind = InterfaceKind.MQTT
    server_languages = ["python", "cpp"]
    client_languages = ["python", "typescript"]
    edge_types = [GraphEdgeType.EXPOSES, GraphEdgeType.CONSUMES]


class DbusStub(_BacklogStub):
    plugin_id = "dbus"
    interface_kind = InterfaceKind.DBUS
    server_languages = ["python", "cpp"]
    client_languages = ["python"]
    edge_types = [GraphEdgeType.IMPLEMENTS, GraphEdgeType.CONSUMES]
