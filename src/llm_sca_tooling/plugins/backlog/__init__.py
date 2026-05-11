"""Backlog interface plugins: gRPC, Protobuf, ZeroMQ, MQTT, and D-Bus."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from llm_sca_tooling.plugins.base import (
    DetectedInterfaceFile,
    InterfacePluginBase,
    PluginConfig,
    PluginDetectResult,
    PluginIndexResult,
    PluginLinkResult,
    TraversalDirection,
    TraversalLink,
)
from llm_sca_tooling.plugins.capability import (
    PluginAvailability,
    PluginCapabilityDescriptor,
)
from llm_sca_tooling.plugins.graph_facts import interface_edge, interface_node
from llm_sca_tooling.plugins.interface_record import (
    InterfaceKind,
    InterfaceOperation,
    InterfaceRecord,
    OperationType,
    make_interface_id,
    make_operation_id,
)
from llm_sca_tooling.schemas.graph import GraphEdgeType, GraphNodeType
from llm_sca_tooling.storage.registry import RepositoryRecord
from llm_sca_tooling.storage.snapshots import SnapshotRecord
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = [
    "DbusPlugin",
    "GrpcPlugin",
    "MqttPlugin",
    "ProtobufPlugin",
    "ZeroMQPlugin",
    "backlog_plugins",
]

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# gRPC / Protobuf: service and message declarations in .proto files
_PROTO_SERVICE_RE = re.compile(r"^service\s+(\w+)\s*\{", re.MULTILINE)
_PROTO_RPC_RE = re.compile(
    r"rpc\s+(\w+)\s*\(([^)]*)\)\s*returns\s*\(([^)]*)\)", re.MULTILINE
)
_PROTO_MESSAGE_RE = re.compile(r"^message\s+(\w+)\s*\{", re.MULTILINE)
_PROTO_FIELD_RE = re.compile(
    r"^\s+(?:repeated\s+)?(\w+)\s+(\w+)\s*=\s*(\d+);", re.MULTILINE
)

# ZeroMQ: socket construction patterns
_ZMQ_SOCKET_RE = re.compile(
    r"\.socket\(\s*(?:zmq\.)?([A-Z_]+)\s*\)|context\.socket\(\s*(?:zmq\.)?([A-Z_]+)\s*\)",  # noqa: E501
    re.IGNORECASE,
)
_ZMQ_TOPIC_RE = re.compile(
    r"\.bind\(['\"]([^'\"]+)['\"]|\.connect\(['\"]([^'\"]+)['\"]"
)
_ZMQ_IMPORT_RE = re.compile(
    r"import\s+zmq|from\s+zmq\s+import|#include\s+[<\"]zmq(?:\.h)?[>\"]"
)

# MQTT: topic pub/sub patterns
_MQTT_IMPORT_RE = re.compile(
    r"import\s+(?:paho\.mqtt|mqtt)|from\s+paho\.mqtt|#include\s+[<\"](?:mqtt|MQTTClient)",  # noqa: E501
    re.IGNORECASE,
)
_MQTT_PUBLISH_RE = re.compile(r"\.publish\(\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
_MQTT_SUBSCRIBE_RE = re.compile(r"\.subscribe\(\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)

# D-Bus: well-known XML and Python/C API patterns
_DBUS_XML_INTERFACE_RE = re.compile(r"<interface\s+name=['\"]([^'\"]+)['\"]")
_DBUS_XML_METHOD_RE = re.compile(r"<method\s+name=['\"]([^'\"]+)['\"]")
_DBUS_PYTHON_RE = re.compile(
    r"dbus\.Interface|bus\.get_object|@dbus\.service\.method"
    r"|dbus_interface=['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def _read_text(path: Path) -> str:
    return path.read_text(errors="replace") if path.exists() else ""


# ---------------------------------------------------------------------------
# gRPC plugin
# ---------------------------------------------------------------------------


class GrpcPlugin(InterfacePluginBase):
    """gRPC interface plugin — detects and indexes .proto service definitions."""

    plugin_id = "grpc"
    plugin_version = "0.1.0"

    async def check_availability(self) -> PluginAvailability:
        return PluginAvailability(plugin_id=self.plugin_id, available=True)

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            interface_kinds=[InterfaceKind.grpc],
            supported_server_languages=["python", "cpp", "go"],
            supported_client_languages=["python", "typescript"],
            emitted_node_types=[GraphNodeType.grpc_service.value],
            emitted_edge_types=[
                GraphEdgeType.exposes.value,
                GraphEdgeType.consumes.value,
            ],
            max_confidence="parser",
        )

    async def detect(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        file_list: list[str],
    ) -> PluginDetectResult:
        if repo is None or snapshot is None:
            return []
        detected: list[DetectedInterfaceFile] = []
        for file_path in file_list:
            path = repo.root_path / file_path
            if path.suffix.lower() == ".proto":
                text = _read_text(path)
                if _PROTO_SERVICE_RE.search(text):
                    detected.append(
                        DetectedInterfaceFile(
                            file_path=file_path,
                            interface_type_hint="proto-service",
                            detection_method="filename+pattern",
                            confidence="parser",
                        )
                    )
        return PluginDetectResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            detected_files=detected,
            detection_confidence="parser" if detected else "heuristic",
            run_stats={"files_scanned": len(file_list)},
        )

    async def index(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        detect_result: PluginDetectResult,
        config: PluginConfig,
    ) -> PluginIndexResult:
        records: list[InterfaceRecord] = []
        diagnostics: list[dict[str, Any]] = []
        for detected in detect_result.detected_files:
            path = repo.root_path / detected.file_path
            text = _read_text(path)
            for svc_match in _PROTO_SERVICE_RE.finditer(text):
                svc_name = svc_match.group(1)
                interface_id = make_interface_id(
                    self.plugin_id, InterfaceKind.grpc, svc_name, repo.repo_id
                )
                operations: list[InterfaceOperation] = []
                for rpc_match in _PROTO_RPC_RE.finditer(text):
                    rpc_name = rpc_match.group(1)
                    op_id = make_operation_id(interface_id, svc_name, rpc_name)
                    operations.append(
                        InterfaceOperation(
                            operation_id=op_id,
                            interface_id=interface_id,
                            name=rpc_name,
                            operation_type=OperationType.method,
                            confidence="parser",
                            binding_method="proto-rpc",
                        )
                    )
                records.append(
                    InterfaceRecord(
                        interface_id=interface_id,
                        kind=InterfaceKind.grpc,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_name=svc_name,
                        definition_files=[detected.file_path],
                        source_repos=[repo.repo_id],
                        operations=operations,
                        confidence="parser",
                        snapshot_ids={repo.repo_id: snapshot.snapshot_id},
                    )
                )
        return PluginIndexResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            interface_records=records,
            diagnostics=diagnostics,
            run_stats={"services": len(records)},
        )

    async def link(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        index_result: PluginIndexResult,
        workspace: WorkspaceStore,
        config: PluginConfig,
    ) -> PluginLinkResult:
        nodes = []
        edges = []
        for record in index_result.interface_records:
            node = interface_node(record, repo, snapshot, GraphNodeType.grpc_service)
            nodes.append(node)
            handlers = await _node_ids_for_file(
                workspace, repo.repo_id, record.definition_files[0]
            )
            for handler_id in handlers[:1]:
                edges.append(
                    interface_edge(
                        repo,
                        snapshot,
                        GraphEdgeType.exposes,
                        handler_id,
                        node.node_id,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_id=record.interface_id,
                        confidence="parser",
                    )
                )
        await workspace.graph.add_nodes(nodes)
        await workspace.graph.add_edges(edges)
        return PluginLinkResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            nodes_emitted=len(nodes),
            edges_emitted=len(edges),
            interface_records_linked=len(index_result.interface_records),
        )

    async def traverse(
        self,
        node_id: str,
        direction: TraversalDirection,
        workspace: WorkspaceStore,
    ) -> list[TraversalLink]:
        graph_slice = await workspace.queries.fetch_neighbours(
            node_id,
            direction=_graph_direction(direction),
            edge_types=[GraphEdgeType.exposes.value, GraphEdgeType.consumes.value],
        )
        return [
            TraversalLink(
                from_node_id=edge.source_id,
                to_node_id=edge.target_id,
                via_interface_id=str(edge.properties.get("interface_id", "")),
                plugin_id=self.plugin_id,
                edge_type=edge.edge_type.value,
                confidence=str(edge.properties.get("binding_confidence", "heuristic")),
                direction=direction,
            )
            for edge in graph_slice.edges
        ]


# ---------------------------------------------------------------------------
# Protobuf plugin
# ---------------------------------------------------------------------------


class ProtobufPlugin(InterfacePluginBase):
    """Protobuf message schema plugin — detects .proto message type definitions."""

    plugin_id = "protobuf"
    plugin_version = "0.1.0"

    async def check_availability(self) -> PluginAvailability:
        return PluginAvailability(plugin_id=self.plugin_id, available=True)

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            interface_kinds=[InterfaceKind.protobuf],
            supported_server_languages=["python", "cpp", "go", "typescript"],
            supported_client_languages=["python", "cpp", "go", "typescript"],
            emitted_node_types=[GraphNodeType.protobuf_message.value],
            emitted_edge_types=[
                GraphEdgeType.implements.value,
                GraphEdgeType.imports.value,
            ],
            max_confidence="parser",
        )

    async def detect(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        file_list: list[str],
    ) -> PluginDetectResult:
        if repo is None or snapshot is None:
            return []
        detected: list[DetectedInterfaceFile] = []
        for file_path in file_list:
            path = repo.root_path / file_path
            if path.suffix.lower() == ".proto":
                text = _read_text(path)
                if _PROTO_MESSAGE_RE.search(text):
                    detected.append(
                        DetectedInterfaceFile(
                            file_path=file_path,
                            interface_type_hint="proto-message",
                            detection_method="filename+pattern",
                            confidence="parser",
                        )
                    )
        return PluginDetectResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            detected_files=detected,
            detection_confidence="parser" if detected else "heuristic",
            run_stats={"files_scanned": len(file_list)},
        )

    async def index(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        detect_result: PluginDetectResult,
        config: PluginConfig,
    ) -> PluginIndexResult:
        records: list[InterfaceRecord] = []
        for detected in detect_result.detected_files:
            path = repo.root_path / detected.file_path
            text = _read_text(path)
            for msg_match in _PROTO_MESSAGE_RE.finditer(text):
                msg_name = msg_match.group(1)
                interface_id = make_interface_id(
                    self.plugin_id, InterfaceKind.protobuf, msg_name, repo.repo_id
                )
                operations: list[InterfaceOperation] = []
                for field_match in _PROTO_FIELD_RE.finditer(text):
                    _field_type, field_name, _field_num = (
                        field_match.group(1),
                        field_match.group(2),
                        field_match.group(3),
                    )
                    op_id = make_operation_id(interface_id, msg_name, field_name)
                    operations.append(
                        InterfaceOperation(
                            operation_id=op_id,
                            interface_id=interface_id,
                            name=field_name,
                            operation_type=OperationType.method,
                            confidence="parser",
                            binding_method="proto-field",
                        )
                    )
                records.append(
                    InterfaceRecord(
                        interface_id=interface_id,
                        kind=InterfaceKind.protobuf,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_name=msg_name,
                        definition_files=[detected.file_path],
                        source_repos=[repo.repo_id],
                        operations=operations,
                        confidence="parser",
                        snapshot_ids={repo.repo_id: snapshot.snapshot_id},
                    )
                )
        return PluginIndexResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            interface_records=records,
            run_stats={"messages": len(records)},
        )

    async def link(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        index_result: PluginIndexResult,
        workspace: WorkspaceStore,
        config: PluginConfig,
    ) -> PluginLinkResult:
        nodes = []
        edges = []
        for record in index_result.interface_records:
            node = interface_node(
                record, repo, snapshot, GraphNodeType.protobuf_message
            )
            nodes.append(node)
            handlers = await _node_ids_for_file(
                workspace, repo.repo_id, record.definition_files[0]
            )
            for handler_id in handlers[:1]:
                edges.append(
                    interface_edge(
                        repo,
                        snapshot,
                        GraphEdgeType.implements,
                        handler_id,
                        node.node_id,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_id=record.interface_id,
                        confidence="parser",
                    )
                )
        await workspace.graph.add_nodes(nodes)
        await workspace.graph.add_edges(edges)
        return PluginLinkResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            nodes_emitted=len(nodes),
            edges_emitted=len(edges),
            interface_records_linked=len(index_result.interface_records),
        )

    async def traverse(
        self,
        node_id: str,
        direction: TraversalDirection,
        workspace: WorkspaceStore,
    ) -> list[TraversalLink]:
        graph_slice = await workspace.queries.fetch_neighbours(
            node_id,
            direction=_graph_direction(direction),
            edge_types=[GraphEdgeType.implements.value, GraphEdgeType.imports.value],
        )
        return [
            TraversalLink(
                from_node_id=edge.source_id,
                to_node_id=edge.target_id,
                via_interface_id=str(edge.properties.get("interface_id", "")),
                plugin_id=self.plugin_id,
                edge_type=edge.edge_type.value,
                confidence=str(edge.properties.get("binding_confidence", "heuristic")),
                direction=direction,
            )
            for edge in graph_slice.edges
        ]


# ---------------------------------------------------------------------------
# ZeroMQ plugin
# ---------------------------------------------------------------------------


class ZeroMQPlugin(InterfacePluginBase):
    """ZeroMQ socket pattern plugin — detects PUB/SUB, REQ/REP, PUSH/PULL patterns."""

    plugin_id = "zeromq"
    plugin_version = "0.1.0"

    async def check_availability(self) -> PluginAvailability:
        return PluginAvailability(plugin_id=self.plugin_id, available=True)

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            interface_kinds=[InterfaceKind.zeromq],
            supported_server_languages=["python", "cpp"],
            supported_client_languages=["python", "typescript"],
            emitted_node_types=[GraphNodeType.interface.value],
            emitted_edge_types=[
                GraphEdgeType.exposes.value,
                GraphEdgeType.consumes.value,
            ],
            max_confidence="analyser",
        )

    async def detect(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        file_list: list[str],
    ) -> PluginDetectResult:
        if repo is None or snapshot is None:
            return []
        detected: list[DetectedInterfaceFile] = []
        for file_path in file_list:
            path = repo.root_path / file_path
            suffix = path.suffix.lower()
            if suffix not in {".py", ".cpp", ".cc", ".cxx", ".h", ".hpp"}:
                continue
            text = _read_text(path)
            if _ZMQ_IMPORT_RE.search(text) and _ZMQ_SOCKET_RE.search(text):
                detected.append(
                    DetectedInterfaceFile(
                        file_path=file_path,
                        interface_type_hint="zmq-socket",
                        detection_method="import+pattern",
                        confidence="analyser",
                    )
                )
        return PluginDetectResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            detected_files=detected,
            detection_confidence="analyser" if detected else "heuristic",
            run_stats={"files_scanned": len(file_list)},
        )

    async def index(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        detect_result: PluginDetectResult,
        config: PluginConfig,
    ) -> PluginIndexResult:
        records: list[InterfaceRecord] = []
        for detected in detect_result.detected_files:
            path = repo.root_path / detected.file_path
            text = _read_text(path)
            for sock_match in _ZMQ_SOCKET_RE.finditer(text):
                sock_type = (
                    sock_match.group(1) or sock_match.group(2) or "UNKNOWN"
                ).upper()
                name = f"zmq:{sock_type}:{detected.file_path}"
                interface_id = make_interface_id(
                    self.plugin_id, InterfaceKind.zeromq, name, repo.repo_id
                )
                operations: list[InterfaceOperation] = []
                # Collect bind/connect endpoints
                for ep_match in _ZMQ_TOPIC_RE.finditer(text):
                    endpoint = ep_match.group(1) or ep_match.group(2) or ""
                    if endpoint:
                        op_id = make_operation_id(interface_id, sock_type, endpoint)
                        operations.append(
                            InterfaceOperation(
                                operation_id=op_id,
                                interface_id=interface_id,
                                name=endpoint,
                                operation_type=OperationType.event,
                                confidence="analyser",
                                binding_method="zmq-endpoint",
                            )
                        )
                records.append(
                    InterfaceRecord(
                        interface_id=interface_id,
                        kind=InterfaceKind.zeromq,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_name=name,
                        definition_files=[detected.file_path],
                        source_repos=[repo.repo_id],
                        operations=operations,
                        confidence="analyser",
                        snapshot_ids={repo.repo_id: snapshot.snapshot_id},
                    )
                )
        return PluginIndexResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            interface_records=records,
            run_stats={"sockets": len(records)},
        )

    async def link(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        index_result: PluginIndexResult,
        workspace: WorkspaceStore,
        config: PluginConfig,
    ) -> PluginLinkResult:
        nodes = []
        edges = []
        for record in index_result.interface_records:
            node = interface_node(record, repo, snapshot, GraphNodeType.interface)
            nodes.append(node)
            handlers = await _node_ids_for_file(
                workspace, repo.repo_id, record.definition_files[0]
            )
            for handler_id in handlers[:1]:
                edges.append(
                    interface_edge(
                        repo,
                        snapshot,
                        GraphEdgeType.exposes,
                        handler_id,
                        node.node_id,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_id=record.interface_id,
                        confidence="analyser",
                    )
                )
        await workspace.graph.add_nodes(nodes)
        await workspace.graph.add_edges(edges)
        return PluginLinkResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            nodes_emitted=len(nodes),
            edges_emitted=len(edges),
            interface_records_linked=len(index_result.interface_records),
        )

    async def traverse(
        self,
        node_id: str,
        direction: TraversalDirection,
        workspace: WorkspaceStore,
    ) -> list[TraversalLink]:
        graph_slice = await workspace.queries.fetch_neighbours(
            node_id,
            direction=_graph_direction(direction),
            edge_types=[GraphEdgeType.exposes.value, GraphEdgeType.consumes.value],
        )
        return [
            TraversalLink(
                from_node_id=edge.source_id,
                to_node_id=edge.target_id,
                via_interface_id=str(edge.properties.get("interface_id", "")),
                plugin_id=self.plugin_id,
                edge_type=edge.edge_type.value,
                confidence=str(edge.properties.get("binding_confidence", "heuristic")),
                direction=direction,
            )
            for edge in graph_slice.edges
        ]


# ---------------------------------------------------------------------------
# MQTT plugin
# ---------------------------------------------------------------------------


class MqttPlugin(InterfacePluginBase):
    """MQTT topic pub/sub plugin — detects publish/subscribe topic patterns."""

    plugin_id = "mqtt"
    plugin_version = "0.1.0"

    async def check_availability(self) -> PluginAvailability:
        return PluginAvailability(plugin_id=self.plugin_id, available=True)

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            interface_kinds=[InterfaceKind.mqtt],
            supported_server_languages=["python", "cpp"],
            supported_client_languages=["python", "typescript"],
            emitted_node_types=[GraphNodeType.interface.value],
            emitted_edge_types=[
                GraphEdgeType.exposes.value,
                GraphEdgeType.consumes.value,
            ],
            max_confidence="analyser",
        )

    async def detect(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        file_list: list[str],
    ) -> PluginDetectResult:
        if repo is None or snapshot is None:
            return []
        detected: list[DetectedInterfaceFile] = []
        for file_path in file_list:
            path = repo.root_path / file_path
            suffix = path.suffix.lower()
            if suffix not in {".py", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".ts", ".js"}:
                continue
            text = _read_text(path)
            if _MQTT_IMPORT_RE.search(text) and (
                _MQTT_PUBLISH_RE.search(text) or _MQTT_SUBSCRIBE_RE.search(text)
            ):
                detected.append(
                    DetectedInterfaceFile(
                        file_path=file_path,
                        interface_type_hint="mqtt-topic",
                        detection_method="import+pattern",
                        confidence="analyser",
                    )
                )
        return PluginDetectResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            detected_files=detected,
            detection_confidence="analyser" if detected else "heuristic",
            run_stats={"files_scanned": len(file_list)},
        )

    async def index(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        detect_result: PluginDetectResult,
        config: PluginConfig,
    ) -> PluginIndexResult:
        records: list[InterfaceRecord] = []
        for detected in detect_result.detected_files:
            path = repo.root_path / detected.file_path
            text = _read_text(path)
            topics: list[tuple[str, str]] = [
                (m.group(1), "publish") for m in _MQTT_PUBLISH_RE.finditer(text)
            ] + [(m.group(1), "subscribe") for m in _MQTT_SUBSCRIBE_RE.finditer(text)]
            for topic, direction in topics:
                name = f"mqtt:{topic}"
                interface_id = make_interface_id(
                    self.plugin_id, InterfaceKind.mqtt, name, repo.repo_id
                )
                op_id = make_operation_id(interface_id, topic, direction)
                op_type = (
                    OperationType.event
                    if direction == "publish"
                    else OperationType.event
                )
                records.append(
                    InterfaceRecord(
                        interface_id=interface_id,
                        kind=InterfaceKind.mqtt,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_name=name,
                        definition_files=[detected.file_path],
                        source_repos=[repo.repo_id],
                        operations=[
                            InterfaceOperation(
                                operation_id=op_id,
                                interface_id=interface_id,
                                name=topic,
                                operation_type=op_type,
                                confidence="analyser",
                                binding_method=f"mqtt-{direction}",
                            )
                        ],
                        confidence="analyser",
                        snapshot_ids={repo.repo_id: snapshot.snapshot_id},
                    )
                )
        return PluginIndexResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            interface_records=records,
            run_stats={"topics": len(records)},
        )

    async def link(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        index_result: PluginIndexResult,
        workspace: WorkspaceStore,
        config: PluginConfig,
    ) -> PluginLinkResult:
        nodes = []
        edges = []
        for record in index_result.interface_records:
            node = interface_node(record, repo, snapshot, GraphNodeType.interface)
            nodes.append(node)
            handlers = await _node_ids_for_file(
                workspace, repo.repo_id, record.definition_files[0]
            )
            op = record.operations[0] if record.operations else None
            edge_type = (
                GraphEdgeType.exposes
                if op and op.operation_type == OperationType.event
                else GraphEdgeType.consumes
            )
            for handler_id in handlers[:1]:
                edges.append(
                    interface_edge(
                        repo,
                        snapshot,
                        edge_type,
                        handler_id,
                        node.node_id,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_id=record.interface_id,
                        operation_name=op.name if op else None,
                        confidence="analyser",
                    )
                )
        await workspace.graph.add_nodes(nodes)
        await workspace.graph.add_edges(edges)
        return PluginLinkResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            nodes_emitted=len(nodes),
            edges_emitted=len(edges),
            interface_records_linked=len(index_result.interface_records),
        )

    async def traverse(
        self,
        node_id: str,
        direction: TraversalDirection,
        workspace: WorkspaceStore,
    ) -> list[TraversalLink]:
        graph_slice = await workspace.queries.fetch_neighbours(
            node_id,
            direction=_graph_direction(direction),
            edge_types=[GraphEdgeType.exposes.value, GraphEdgeType.consumes.value],
        )
        return [
            TraversalLink(
                from_node_id=edge.source_id,
                to_node_id=edge.target_id,
                via_interface_id=str(edge.properties.get("interface_id", "")),
                plugin_id=self.plugin_id,
                edge_type=edge.edge_type.value,
                confidence=str(edge.properties.get("binding_confidence", "heuristic")),
                direction=direction,
            )
            for edge in graph_slice.edges
        ]


# ---------------------------------------------------------------------------
# D-Bus plugin
# ---------------------------------------------------------------------------


class DbusPlugin(InterfacePluginBase):
    """D-Bus interface plugin.

    Detects XML introspection files and Python D-Bus APIs.
    """

    plugin_id = "dbus"
    plugin_version = "0.1.0"

    async def check_availability(self) -> PluginAvailability:
        return PluginAvailability(plugin_id=self.plugin_id, available=True)

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            interface_kinds=[InterfaceKind.dbus],
            supported_server_languages=["python", "cpp"],
            supported_client_languages=["python"],
            emitted_node_types=[GraphNodeType.idl_interface.value],
            emitted_edge_types=[
                GraphEdgeType.exposes.value,
                GraphEdgeType.consumes.value,
            ],
            max_confidence="parser",
        )

    async def detect(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        file_list: list[str],
    ) -> PluginDetectResult:
        if repo is None or snapshot is None:
            return []
        detected: list[DetectedInterfaceFile] = []
        for file_path in file_list:
            path = repo.root_path / file_path
            suffix = path.suffix.lower()
            if suffix == ".xml":
                text = _read_text(path)
                if _DBUS_XML_INTERFACE_RE.search(text):
                    detected.append(
                        DetectedInterfaceFile(
                            file_path=file_path,
                            interface_type_hint="dbus-xml",
                            detection_method="xml-pattern",
                            confidence="parser",
                        )
                    )
            elif suffix == ".py":
                text = _read_text(path)
                if _DBUS_PYTHON_RE.search(text):
                    detected.append(
                        DetectedInterfaceFile(
                            file_path=file_path,
                            interface_type_hint="dbus-python",
                            detection_method="api-pattern",
                            confidence="analyser",
                        )
                    )
        return PluginDetectResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            detected_files=detected,
            detection_confidence=(
                "parser"
                if any(d.confidence == "parser" for d in detected)
                else "analyser"
            ),
            run_stats={"files_scanned": len(file_list)},
        )

    async def index(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        detect_result: PluginDetectResult,
        config: PluginConfig,
    ) -> PluginIndexResult:
        records: list[InterfaceRecord] = []
        diagnostics: list[dict[str, Any]] = []
        for detected in detect_result.detected_files:
            path = repo.root_path / detected.file_path
            if detected.interface_type_hint == "dbus-xml":
                try:
                    records.extend(
                        _parse_dbus_xml(
                            path,
                            detected.file_path,
                            repo.repo_id,
                            snapshot.snapshot_id,
                            self.plugin_id,
                            self.plugin_version,
                        )
                    )
                except ET.ParseError as exc:
                    diagnostics.append(
                        {"code": "DBUS_XML_PARSE_FAILED", "message": str(exc)}
                    )
            else:
                # Python API pattern — extract interface names
                text = _read_text(path)
                for m in _DBUS_PYTHON_RE.finditer(text):
                    iface_name = m.group(1)
                    if not iface_name:
                        continue
                    interface_id = make_interface_id(
                        self.plugin_id, InterfaceKind.dbus, iface_name, repo.repo_id
                    )
                    records.append(
                        InterfaceRecord(
                            interface_id=interface_id,
                            kind=InterfaceKind.dbus,
                            plugin_id=self.plugin_id,
                            plugin_version=self.plugin_version,
                            interface_name=iface_name,
                            definition_files=[detected.file_path],
                            source_repos=[repo.repo_id],
                            operations=[],
                            confidence="analyser",
                            snapshot_ids={repo.repo_id: snapshot.snapshot_id},
                        )
                    )
        return PluginIndexResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            interface_records=records,
            diagnostics=diagnostics,
            run_stats={"interfaces": len(records)},
        )

    async def link(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        index_result: PluginIndexResult,
        workspace: WorkspaceStore,
        config: PluginConfig,
    ) -> PluginLinkResult:
        nodes = []
        edges = []
        for record in index_result.interface_records:
            node = interface_node(record, repo, snapshot, GraphNodeType.idl_interface)
            nodes.append(node)
            handlers = await _node_ids_for_file(
                workspace, repo.repo_id, record.definition_files[0]
            )
            for handler_id in handlers[:1]:
                edges.append(
                    interface_edge(
                        repo,
                        snapshot,
                        GraphEdgeType.exposes,
                        handler_id,
                        node.node_id,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_id=record.interface_id,
                        confidence=record.confidence,
                    )
                )
        await workspace.graph.add_nodes(nodes)
        await workspace.graph.add_edges(edges)
        return PluginLinkResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            nodes_emitted=len(nodes),
            edges_emitted=len(edges),
            interface_records_linked=len(index_result.interface_records),
        )

    async def traverse(
        self,
        node_id: str,
        direction: TraversalDirection,
        workspace: WorkspaceStore,
    ) -> list[TraversalLink]:
        graph_slice = await workspace.queries.fetch_neighbours(
            node_id,
            direction=_graph_direction(direction),
            edge_types=[GraphEdgeType.exposes.value, GraphEdgeType.consumes.value],
        )
        return [
            TraversalLink(
                from_node_id=edge.source_id,
                to_node_id=edge.target_id,
                via_interface_id=str(edge.properties.get("interface_id", "")),
                plugin_id=self.plugin_id,
                edge_type=edge.edge_type.value,
                confidence=str(edge.properties.get("binding_confidence", "heuristic")),
                direction=direction,
            )
            for edge in graph_slice.edges
        ]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _graph_direction(direction: TraversalDirection) -> str:
    if direction == TraversalDirection.outbound:
        return "out"
    if direction == TraversalDirection.inbound:
        return "in"
    return "both"


async def _node_ids_for_file(
    workspace: WorkspaceStore, repo_id: str, file_path: str
) -> list[str]:
    graph_slice = await workspace.queries.fetch_by_file(repo_id, file_path)
    code_types = {GraphNodeType.function, GraphNodeType.method, GraphNodeType.class_}
    code_nodes = [n.node_id for n in graph_slice.nodes if n.node_type in code_types]
    return code_nodes or [n.node_id for n in graph_slice.nodes]


def _parse_dbus_xml(
    path: Path,
    rel_path: str,
    repo_id: str,
    snapshot_id: str,
    plugin_id: str,
    plugin_version: str,
) -> list[InterfaceRecord]:
    text = _read_text(path)
    root = ET.fromstring(text)  # noqa: S314  # nosec B314
    records: list[InterfaceRecord] = []
    for iface_elem in root.iter("interface"):
        iface_name = iface_elem.get("name", "")
        if not iface_name:
            continue
        interface_id = make_interface_id(
            plugin_id, InterfaceKind.dbus, iface_name, repo_id
        )
        operations: list[InterfaceOperation] = []
        for method_elem in iface_elem.findall("method"):
            method_name = method_elem.get("name", "")
            if method_name:
                op_id = make_operation_id(interface_id, iface_name, method_name)
                operations.append(
                    InterfaceOperation(
                        operation_id=op_id,
                        interface_id=interface_id,
                        name=method_name,
                        operation_type=OperationType.method,
                        confidence="parser",
                        binding_method="dbus-xml-method",
                    )
                )
        for signal_elem in iface_elem.findall("signal"):
            signal_name = signal_elem.get("name", "")
            if signal_name:
                op_id = make_operation_id(interface_id, iface_name, signal_name)
                operations.append(
                    InterfaceOperation(
                        operation_id=op_id,
                        interface_id=interface_id,
                        name=signal_name,
                        operation_type=OperationType.event,
                        confidence="parser",
                        binding_method="dbus-xml-signal",
                    )
                )
        records.append(
            InterfaceRecord(
                interface_id=interface_id,
                kind=InterfaceKind.dbus,
                plugin_id=plugin_id,
                plugin_version=plugin_version,
                interface_name=iface_name,
                definition_files=[rel_path],
                source_repos=[repo_id],
                operations=operations,
                confidence="parser",
                snapshot_ids={repo_id: snapshot_id},
            )
        )
    return records


def backlog_plugins() -> list[InterfacePluginBase]:
    return [GrpcPlugin(), ProtobufPlugin(), ZeroMQPlugin(), MqttPlugin(), DbusPlugin()]
