"""Socket.IO/WebSocket interface plugin."""

from __future__ import annotations

import re

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

__all__ = ["WebSocketPlugin"]


class WebSocketPlugin(InterfacePluginBase):
    plugin_id = "websocket"
    plugin_version = "0.1.0"

    async def check_availability(self) -> PluginAvailability:
        return PluginAvailability(plugin_id=self.plugin_id, available=True)

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            interface_kinds=[InterfaceKind.websocket],
            supported_server_languages=["python"],
            supported_client_languages=["typescript", "javascript"],
            emitted_node_types=[GraphNodeType.websocket_event.value],
            emitted_edge_types=[
                GraphEdgeType.exposes.value,
                GraphEdgeType.consumes.value,
            ],
            max_confidence="analyser",
            incremental_support=True,
        )

    async def detect(
        self, repo: RepositoryRecord, snapshot: SnapshotRecord, file_list: list[str]
    ) -> PluginDetectResult:
        detected = []
        for file_path in file_list:
            text = (repo.root_path / file_path).read_text(errors="replace")
            if _SOCKET_RE.search(text):
                detected.append(
                    DetectedInterfaceFile(
                        file_path=file_path,
                        interface_type_hint="socketio",
                        detection_method="socketio-pattern",
                        confidence="analyser",
                    )
                )
        return PluginDetectResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            detected_files=detected,
            detection_confidence="analyser",
        )

    async def index(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        detect_result: PluginDetectResult,
        config: PluginConfig,
    ) -> PluginIndexResult:
        servers: dict[str, str] = {}
        clients: dict[str, str] = {}
        for detected in detect_result.detected_files:
            text = (repo.root_path / detected.file_path).read_text(errors="replace")
            for match in _SERVER_RE.finditer(text):
                servers[match.group("event")] = detected.file_path
            for match in _CLIENT_RE.finditer(text):
                clients[match.group("event")] = detected.file_path
        records = []
        for event, server_file in servers.items():
            interface_name = f"/:{event}"
            interface_id = make_interface_id(
                self.plugin_id, InterfaceKind.websocket, interface_name, repo.repo_id
            )
            op = InterfaceOperation(
                operation_id=make_operation_id(interface_id, event, "WS"),
                interface_id=interface_id,
                name=event,
                operation_type=OperationType.event,
                http_method="WS",
                server_handler_node_ids=[],
                client_callsite_node_ids=[clients[event]] if event in clients else [],
                confidence="analyser",
                binding_method="socketio-event",
            )
            records.append(
                InterfaceRecord(
                    interface_id=interface_id,
                    kind=InterfaceKind.websocket,
                    plugin_id=self.plugin_id,
                    plugin_version=self.plugin_version,
                    interface_name=interface_name,
                    definition_files=[server_file],
                    source_repos=[repo.repo_id],
                    operations=[op],
                    confidence="analyser",
                    snapshot_ids={repo.repo_id: snapshot.snapshot_id},
                )
            )
        return PluginIndexResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            interface_records=records,
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
            event_node = interface_node(
                record, repo, snapshot, GraphNodeType.websocket_event
            )
            nodes.append(event_node)
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
                        event_node.node_id,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_id=record.interface_id,
                        operation_name=record.operations[0].name,
                        confidence=record.confidence,
                    )
                )
            for client_file in list(record.operations[0].client_callsite_node_ids):
                clients = await _node_ids_for_file(workspace, repo.repo_id, client_file)
                record.operations[0].client_callsite_node_ids[:] = clients[:1]
                for client_id in clients[:1]:
                    edges.append(
                        interface_edge(
                            repo,
                            snapshot,
                            GraphEdgeType.consumes,
                            client_id,
                            event_node.node_id,
                            plugin_id=self.plugin_id,
                            plugin_version=self.plugin_version,
                            interface_id=record.interface_id,
                            operation_name=record.operations[0].name,
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
        self, node_id: str, direction: TraversalDirection, workspace: WorkspaceStore
    ) -> list[TraversalLink]:
        graph_slice = await workspace.queries.fetch_neighbours(
            node_id,
            direction="both",
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
                operation_name=(
                    edge.properties.get("operation_name")
                    if isinstance(edge.properties.get("operation_name"), str)
                    else None
                ),
                direction=direction,
            )
            for edge in graph_slice.edges
        ]


_SOCKET_RE = re.compile(r"socket(?:io)?\.|socket\.|emit\(|@(?:\w+\.)?on\(", re.I)
_SERVER_RE = re.compile(r"@(?:\w+\.)?on\(['\"](?P<event>[^'\"]+)")
_CLIENT_RE = re.compile(r"socket\.(?:on|emit)\(['\"](?P<event>[^'\"]+)")


async def _node_ids_for_file(
    workspace: WorkspaceStore, repo_id: str, file_path: str
) -> list[str]:
    graph_slice = await workspace.queries.fetch_by_file(repo_id, file_path)
    code_types = {GraphNodeType.function, GraphNodeType.method, GraphNodeType.module}
    return [n.node_id for n in graph_slice.nodes if n.node_type in code_types]
