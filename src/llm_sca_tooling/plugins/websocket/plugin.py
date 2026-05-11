"""WebSocket/socket.io plugin orchestration."""

from __future__ import annotations

from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.plugins.base import (
    AmbiguousLinkRecord,
    DetectedInterfaceFile,
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
    OperationType,
    PluginAvailability,
    PluginCapabilityDescriptor,
    TraversalDirection,
)
from llm_sca_tooling.plugins.graph_utils import (
    find_symbol_by_name,
    plugin_edge,
    plugin_node,
    synthetic_symbol,
)
from llm_sca_tooling.plugins.interface_record import (
    InterfaceOperation,
    InterfaceRecord,
    interface_id_for,
    operation_id_for,
)
from llm_sca_tooling.plugins.traverse_edges import traverse_interface_edges
from llm_sca_tooling.plugins.websocket.client_detector import detect_client_events
from llm_sca_tooling.plugins.websocket.event_extractor import match_events
from llm_sca_tooling.plugins.websocket.server_detector import detect_server_events
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.graph_store import GraphStore


class WebSocketPlugin(InterfacePluginBase):
    plugin_id = "websocket"
    plugin_version = "0.1.0"
    interface_kind = InterfaceKind.WEBSOCKET

    def check_availability(self) -> PluginAvailability:
        return PluginAvailability(plugin_id=self.plugin_id, available=True)

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            interface_kinds=[InterfaceKind.WEBSOCKET],
            supported_server_languages=["python"],
            supported_client_languages=["typescript", "javascript"],
            emitted_node_types=[GraphNodeType.WEBSOCKET_EVENT, GraphNodeType.FUNCTION],
            emitted_edge_types=[
                GraphEdgeType.EXPOSES,
                GraphEdgeType.CONSUMES,
                GraphEdgeType.IMPLEMENTS,
                GraphEdgeType.FFI,
            ],
            max_confidence=ConfidenceLevel.PARSER,
            incremental_support=True,
        )

    def detect(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        file_list: list[ScannedFile],
        config: PluginConfig,
    ) -> PluginDetectResult:
        result = PluginDetectResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.worktree_snapshot_id
            or snapshot.git_sha
            or snapshot.captured_ts,
        )
        for file in file_list:
            if file.language == "python":
                text = file.abs_path.read_text(encoding="utf-8")
                if "socketio" in text or "@socketio.on" in text:
                    result.detected_files.append(
                        DetectedInterfaceFile.create(
                            file.path,
                            "socketio_server",
                            "pattern_match",
                            ConfidenceLevel.ANALYSER,
                        )
                    )
            elif file.language in {"typescript", "javascript"}:
                text = file.abs_path.read_text(encoding="utf-8")
                if "socket.io" in text or "socket.emit" in text or "socket.on" in text:
                    result.detected_files.append(
                        DetectedInterfaceFile.create(
                            file.path,
                            "socketio_client",
                            "pattern_match",
                            ConfidenceLevel.ANALYSER,
                        )
                    )
        return result

    def index(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        detect_result: PluginDetectResult,
        config: PluginConfig,
    ) -> PluginIndexResult:
        result = PluginIndexResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=detect_result.snapshot_id,
        )
        provenance = make_provenance(
            source_tool=self.plugin_id,
            repo=repo,
            snapshot=snapshot,
            source_run_id=config.run_id,
        )
        servers = []
        clients = []
        for detected in detect_result.detected_files:
            text = (config.repo_root / detected.file_path).read_text(encoding="utf-8")
            if detected.interface_type_hint == "socketio_server":
                servers.extend(detect_server_events(text, detected.file_path))
            else:
                clients.extend(detect_client_events(text, detected.file_path))
        records = {}
        for server in servers:
            name = f"{server['namespace']}:{server['event']}"
            interface_id = interface_id_for(
                self.plugin_id, InterfaceKind.WEBSOCKET, name, repo.repo_id
            )
            op = InterfaceOperation(
                operation_id=operation_id_for(interface_id, server["event"], "WS"),
                interface_id=interface_id,
                name=server["event"],
                operation_type=OperationType.EVENT,
                http_method="WS",
                path_pattern=name,
                confidence=server["confidence"],
                binding_method="socketio_ast",
                metadata={"servers": [server], "clients": []},
            )
            records[name] = InterfaceRecord(
                interface_id=interface_id,
                kind=InterfaceKind.WEBSOCKET,
                plugin_id=self.plugin_id,
                plugin_version=self.plugin_version,
                interface_name=name,
                definition_files=[server["file_path"]],
                source_repos=[repo.repo_id],
                operations=[op],
                confidence=server["confidence"],
                snapshot_ids={repo.repo_id: detect_result.snapshot_id},
                provenance=provenance,
            )
        for client in clients:
            matched = False
            for record in records.values():
                confidence = match_events(
                    record.operations[0].metadata["servers"][0], client
                )
                if confidence:
                    record.operations[0].metadata["clients"].append(client)
                    record.operations[0].confidence = confidence
                    matched = True
            if not matched and client["confidence"] == ConfidenceLevel.HEURISTIC:
                name = f"{client['namespace']}:{client['event']}"
                interface_id = interface_id_for(
                    self.plugin_id, InterfaceKind.WEBSOCKET, name, repo.repo_id
                )
                op = InterfaceOperation(
                    operation_id=operation_id_for(interface_id, client["event"], "WS"),
                    interface_id=interface_id,
                    name=client["event"],
                    operation_type=OperationType.EVENT,
                    http_method="WS",
                    path_pattern=name,
                    confidence=ConfidenceLevel.HEURISTIC,
                    binding_method="socketio_client",
                    metadata={"servers": [], "clients": [client]},
                )
                records[name] = InterfaceRecord(
                    interface_id=interface_id,
                    kind=InterfaceKind.WEBSOCKET,
                    plugin_id=self.plugin_id,
                    plugin_version=self.plugin_version,
                    interface_name=name,
                    definition_files=[client["file_path"]],
                    source_repos=[repo.repo_id],
                    operations=[op],
                    confidence=ConfidenceLevel.HEURISTIC,
                    snapshot_ids={repo.repo_id: detect_result.snapshot_id},
                    provenance=provenance,
                )
        result.interface_records = list(records.values())
        return result

    def link(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        index_result: PluginIndexResult,
        graph_store: GraphStore,
        config: PluginConfig,
    ) -> PluginLinkResult:
        result = PluginLinkResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=index_result.snapshot_id,
        )
        for record in index_result.interface_records:
            operation = record.operations[0]
            event_node = plugin_node(
                repo,
                snapshot,
                plugin_id=self.plugin_id,
                plugin_version=self.plugin_version,
                node_type=GraphNodeType.WEBSOCKET_EVENT,
                key=record.interface_name,
                label=record.interface_name,
                interface_id=record.interface_id,
                file_path=(
                    record.definition_files[0] if record.definition_files else None
                ),
                confidence=operation.confidence,
                properties={
                    "event": operation.name,
                    "namespace": operation.path_pattern,
                },
                run_id=config.run_id,
            )
            graph_store.upsert_node(event_node)
            result.nodes.append(event_node)
            server_nodes = []
            for server in operation.metadata.get("servers", []):
                source = find_symbol_by_name(
                    graph_store, repo.repo_id, server["file_path"], server["handler"]
                ) or synthetic_symbol(
                    repo,
                    snapshot,
                    server["file_path"],
                    server["handler"],
                    server["line"],
                    "python",
                    self.plugin_id,
                    self.plugin_version,
                    config.run_id,
                )
                graph_store.upsert_node(source)
                result.nodes.append(source)
                edge = plugin_edge(
                    repo,
                    snapshot,
                    plugin_id=self.plugin_id,
                    plugin_version=self.plugin_version,
                    edge_type=GraphEdgeType.EXPOSES,
                    source_id=source.node_id,
                    target_id=event_node.node_id,
                    interface_id=record.interface_id,
                    operation_name=operation.name,
                    confidence=operation.confidence,
                    run_id=config.run_id,
                )
                graph_store.upsert_edge(edge)
                result.edges.append(edge)
                implements_edge = plugin_edge(
                    repo,
                    snapshot,
                    plugin_id=self.plugin_id,
                    plugin_version=self.plugin_version,
                    edge_type=GraphEdgeType.IMPLEMENTS,
                    source_id=source.node_id,
                    target_id=event_node.node_id,
                    interface_id=record.interface_id,
                    operation_name=operation.name,
                    confidence=operation.confidence,
                    run_id=config.run_id,
                )
                graph_store.upsert_edge(implements_edge)
                result.edges.append(implements_edge)
                server_nodes.append(source)
            for client in operation.metadata.get("clients", []):
                client_lang = (
                    "typescript"
                    if client["file_path"].endswith((".ts", ".tsx"))
                    else "javascript"
                )
                client_node = synthetic_symbol(
                    repo,
                    snapshot,
                    client["file_path"],
                    client["handler"],
                    client["line"],
                    client_lang,
                    self.plugin_id,
                    self.plugin_version,
                    config.run_id,
                )
                graph_store.upsert_node(client_node)
                result.nodes.append(client_node)
                edge = plugin_edge(
                    repo,
                    snapshot,
                    plugin_id=self.plugin_id,
                    plugin_version=self.plugin_version,
                    edge_type=GraphEdgeType.CONSUMES,
                    source_id=client_node.node_id,
                    target_id=event_node.node_id,
                    interface_id=record.interface_id,
                    operation_name=operation.name,
                    confidence=client["confidence"],
                    run_id=config.run_id,
                )
                graph_store.upsert_edge(edge)
                result.edges.append(edge)
                for server_node in server_nodes:
                    ffi_edge = plugin_edge(
                        repo,
                        snapshot,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        edge_type=GraphEdgeType.FFI,
                        source_id=server_node.node_id,
                        target_id=client_node.node_id,
                        interface_id=record.interface_id,
                        operation_name=operation.name,
                        confidence=client["confidence"],
                        run_id=config.run_id,
                    )
                    graph_store.upsert_edge(ffi_edge)
                    result.edges.append(ffi_edge)
                if client["confidence"] == ConfidenceLevel.HEURISTIC:
                    result.ambiguous_links.append(
                        AmbiguousLinkRecord(
                            interface_id=record.interface_id,
                            operation_name=operation.name,
                            candidate_node_ids=[client_node.node_id],
                            reason="dynamic_event_name",
                        )
                    )
        result.nodes_emitted = len(result.nodes)
        result.edges_emitted = len(result.edges)
        result.interface_records_linked = len(index_result.interface_records)
        return result

    def traverse(
        self, node_id: str, direction: TraversalDirection, graph_store: GraphStore
    ) -> list[TraversalLink]:
        return traverse_interface_edges(self.plugin_id, node_id, direction, graph_store)
