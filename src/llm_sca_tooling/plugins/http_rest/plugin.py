"""HTTP/REST interface plugin orchestration."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.plugins.base import AmbiguousLinkRecord, DetectedInterfaceFile, InterfacePluginBase, PluginConfig, PluginDetectResult, PluginIndexResult, PluginLinkResult, TraversalLink
from llm_sca_tooling.plugins.capability import ConfidenceLevel, InterfaceKind, OperationType, PluginAvailability, PluginCapabilityDescriptor, TraversalDirection
from llm_sca_tooling.plugins.graph_utils import find_symbol_by_name, plugin_edge, plugin_node, synthetic_symbol
from llm_sca_tooling.plugins.http_rest.client_detector import detect_http_clients
from llm_sca_tooling.plugins.http_rest.framework_detector import detect_python_routes
from llm_sca_tooling.plugins.http_rest.openapi_parser import parse_openapi_file
from llm_sca_tooling.plugins.http_rest.url_normalizer import match_patterns, normalize_url_pattern
from llm_sca_tooling.plugins.interface_record import InterfaceOperation, InterfaceRecord, interface_id_for, operation_id_for
from llm_sca_tooling.plugins.traverse_edges import traverse_interface_edges
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType, Severity
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.graph_store import GraphStore


class HttpRestPlugin(InterfacePluginBase):
    plugin_id = "http-rest"
    plugin_version = "0.1.0"
    interface_kind = InterfaceKind.HTTP

    def check_availability(self) -> PluginAvailability:
        return PluginAvailability(plugin_id=self.plugin_id, available=True)

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            interface_kinds=[InterfaceKind.HTTP],
            supported_server_languages=["python"],
            supported_client_languages=["typescript", "javascript"],
            emitted_node_types=[GraphNodeType.HTTP_ROUTE, GraphNodeType.FUNCTION],
            emitted_edge_types=[GraphEdgeType.EXPOSES, GraphEdgeType.CONSUMES],
            max_confidence=ConfidenceLevel.PARSER,
            incremental_support=True,
        )

    def detect(self, repo: RepoRef, snapshot: SnapshotRef, file_list: list[ScannedFile], config: PluginConfig) -> PluginDetectResult:
        result = PluginDetectResult(plugin_id=self.plugin_id, repo_id=repo.repo_id, snapshot_id=snapshot.worktree_snapshot_id or snapshot.git_sha or snapshot.captured_ts)
        for file in file_list:
            if file.path.endswith(("openapi.yaml", "openapi.yml", "openapi.json", "swagger.yaml", "swagger.yml", "swagger.json")):
                result.detected_files.append(DetectedInterfaceFile.create(file.path, "openapi", "filename", ConfidenceLevel.PARSER))
                continue
            if file.language == "python":
                text = file.abs_path.read_text(encoding="utf-8")
                if any(token in text for token in ("@app.get", "@router.get", "@app.post", "@app.route", "urlpatterns", "path(")):
                    result.detected_files.append(DetectedInterfaceFile.create(file.path, "python_route", "pattern_match", ConfidenceLevel.ANALYSER))
            elif file.language in {"typescript", "javascript"}:
                text = file.abs_path.read_text(encoding="utf-8")
                if any(token in text for token in ("fetch(", "axios.", "XMLHttpRequest")):
                    result.detected_files.append(DetectedInterfaceFile.create(file.path, "http_client", "pattern_match", ConfidenceLevel.ANALYSER))
        result.run_stats.files_scanned = len(file_list)
        return result

    def index(self, repo: RepoRef, snapshot: SnapshotRef, detect_result: PluginDetectResult, config: PluginConfig) -> PluginIndexResult:
        result = PluginIndexResult(plugin_id=self.plugin_id, repo_id=repo.repo_id, snapshot_id=detect_result.snapshot_id)
        provenance = make_provenance(source_tool=self.plugin_id, repo=repo, snapshot=snapshot, source_run_id=config.run_id)
        route_records: dict[tuple[str, str], InterfaceRecord] = {}
        client_records: list[dict] = []
        for detected in detect_result.detected_files:
            path = config.repo_root / detected.file_path
            if detected.interface_type_hint == "openapi":
                for record in parse_openapi_file(path, repo_id=repo.repo_id, plugin_id=self.plugin_id, plugin_version=self.plugin_version, provenance=provenance, snapshot_id=detect_result.snapshot_id):
                    route_records[(record.operations[0].http_method or "GET", record.operations[0].path_pattern or record.interface_name)] = record
            elif detected.interface_type_hint == "python_route":
                for route in detect_python_routes(path.read_text(encoding="utf-8"), detected.file_path):
                    record = self._record_for_route(repo, detect_result.snapshot_id, provenance, detected.file_path, route)
                    route_records[(record.operations[0].http_method or "GET", record.operations[0].path_pattern or record.interface_name)] = record
            elif detected.interface_type_hint == "http_client":
                client_records.extend(detect_http_clients(path.read_text(encoding="utf-8"), detected.file_path))
        for client in client_records:
            matched = False
            for record in route_records.values():
                operation = record.operations[0]
                match = match_patterns(client["path"], operation.path_pattern or "")
                if match and client["method"] == (operation.http_method or client["method"]):
                    operation.client_callsite_node_ids.append(f"pending:{client['file_path']}:{client['line']}")
                    operation.metadata.setdefault("clients", []).append(client)
                    operation.confidence = ConfidenceLevel(match)
                    matched = True
            if not matched:
                result.diagnostics.append(IndexDiagnostic(diagnostic_id=f"diag:http-rest:unmatched:{len(result.diagnostics)}", severity=Severity.INFO, code="HTTP_CLIENT_UNMATCHED", message=f"HTTP client URL did not match a route: {client['raw_url']}", file_path=client["file_path"], details={"path": client["path"]}))
        result.interface_records = list(route_records.values())
        result.run_stats.files_scanned = len(detect_result.detected_files)
        return result

    def link(self, repo: RepoRef, snapshot: SnapshotRef, index_result: PluginIndexResult, graph_store: GraphStore, config: PluginConfig) -> PluginLinkResult:
        result = PluginLinkResult(plugin_id=self.plugin_id, repo_id=repo.repo_id, snapshot_id=index_result.snapshot_id)
        for record in index_result.interface_records:
            for operation in record.operations:
                route_node = plugin_node(repo, snapshot, plugin_id=self.plugin_id, plugin_version=self.plugin_version, node_type=GraphNodeType.HTTP_ROUTE, key=record.interface_name, label=record.interface_name, interface_id=record.interface_id, file_path=record.definition_files[0] if record.definition_files else None, confidence=operation.confidence, properties={"kind": "http_route", "method": operation.http_method, "path_pattern": operation.path_pattern}, run_id=config.run_id)
                graph_store.upsert_node(route_node)
                result.nodes.append(route_node)
                for handler in operation.metadata.get("handlers", []):
                    handler_node = find_symbol_by_name(graph_store, repo.repo_id, handler["file_path"], handler["handler"])
                    if handler_node is None:
                        handler_node = synthetic_symbol(repo, snapshot, handler["file_path"], handler["handler"], handler["line"], "python", self.plugin_id, self.plugin_version, config.run_id)
                        graph_store.upsert_node(handler_node)
                        result.nodes.append(handler_node)
                    operation.server_handler_node_ids.append(handler_node.node_id)
                    edge = plugin_edge(repo, snapshot, plugin_id=self.plugin_id, plugin_version=self.plugin_version, edge_type=GraphEdgeType.EXPOSES, source_id=handler_node.node_id, target_id=route_node.node_id, interface_id=record.interface_id, operation_name=operation.name, confidence=operation.confidence, run_id=config.run_id)
                    graph_store.upsert_edge(edge)
                    result.edges.append(edge)
                for client in operation.metadata.get("clients", []):
                    client_node = synthetic_symbol(repo, snapshot, client["file_path"], f"{client['source']}:{client['method']} {client['path']}", client["line"], "typescript" if client["file_path"].endswith((".ts", ".tsx")) else "javascript", self.plugin_id, self.plugin_version, config.run_id)
                    graph_store.upsert_node(client_node)
                    result.nodes.append(client_node)
                    operation.client_callsite_node_ids.append(client_node.node_id)
                    confidence = client["confidence"] if isinstance(client["confidence"], ConfidenceLevel) else ConfidenceLevel(str(client["confidence"]))
                    edge = plugin_edge(repo, snapshot, plugin_id=self.plugin_id, plugin_version=self.plugin_version, edge_type=GraphEdgeType.CONSUMES, source_id=client_node.node_id, target_id=route_node.node_id, interface_id=record.interface_id, operation_name=operation.name, confidence=confidence, run_id=config.run_id)
                    graph_store.upsert_edge(edge)
                    result.edges.append(edge)
                    if confidence == ConfidenceLevel.HEURISTIC:
                        result.ambiguous_links.append(AmbiguousLinkRecord(interface_id=record.interface_id, operation_name=operation.name, candidate_node_ids=[client_node.node_id], reason="dynamic_or_prefix_url", confidence=confidence))
            result.interface_records_linked += 1
        result.nodes_emitted = len(result.nodes)
        result.edges_emitted = len(result.edges)
        result.run_stats.nodes_emitted = result.nodes_emitted
        result.run_stats.edges_emitted = result.edges_emitted
        return result

    def traverse(self, node_id: str, direction: TraversalDirection, graph_store: GraphStore) -> list[TraversalLink]:
        return traverse_interface_edges(self.plugin_id, node_id, direction, graph_store)

    def _record_for_route(self, repo: RepoRef, snapshot_id: str, provenance, file_path: str, route: dict) -> InterfaceRecord:
        canonical = normalize_url_pattern(route["path"])
        name = f"{route['method']} {canonical}"
        interface_id = interface_id_for(self.plugin_id, InterfaceKind.HTTP, name, repo.repo_id)
        operation = InterfaceOperation(
            operation_id=operation_id_for(interface_id, canonical, route["method"]),
            interface_id=interface_id,
            name=canonical,
            operation_type=OperationType.ROUTE,
            http_method=route["method"],
            path_pattern=canonical,
            confidence=ConfidenceLevel(route.get("confidence", "analyser")),
            binding_method=route.get("framework", "framework_ast"),
            metadata={"handlers": [route]},
        )
        return InterfaceRecord(interface_id=interface_id, kind=InterfaceKind.HTTP, plugin_id=self.plugin_id, plugin_version=self.plugin_version, interface_name=name, definition_files=[file_path], source_repos=[repo.repo_id], operations=[operation], confidence=operation.confidence, snapshot_ids={repo.repo_id: snapshot_id}, provenance=provenance)
