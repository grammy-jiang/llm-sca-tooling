"""HTTP-REST interface plugin."""

from __future__ import annotations

import re
from pathlib import Path

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
from llm_sca_tooling.plugins.http_rest.openapi_parser import parse_openapi_file
from llm_sca_tooling.plugins.http_rest.url_normalizer import (
    match_paths,
    normalize_url_path,
)
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

__all__ = ["HttpRestPlugin"]


class HttpRestPlugin(InterfacePluginBase):
    plugin_id = "http-rest"
    plugin_version = "0.1.0"

    async def check_availability(self) -> PluginAvailability:
        return PluginAvailability(plugin_id=self.plugin_id, available=True)

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            interface_kinds=[InterfaceKind.http],
            supported_server_languages=["python"],
            supported_client_languages=["typescript", "javascript"],
            emitted_node_types=[GraphNodeType.http_route.value],
            emitted_edge_types=[
                GraphEdgeType.exposes.value,
                GraphEdgeType.consumes.value,
            ],
            max_confidence="parser",
            incremental_support=True,
        )

    async def detect(
        self, repo: RepositoryRecord, snapshot: SnapshotRecord, file_list: list[str]
    ) -> PluginDetectResult:
        detected: list[DetectedInterfaceFile] = []
        for file_path in file_list:
            path = repo.root_path / file_path
            suffix = path.suffix.lower()
            text = _read_text(path)
            if path.name in {"openapi.yaml", "openapi.json", "swagger.json"}:
                detected.append(
                    DetectedInterfaceFile(
                        file_path=file_path,
                        interface_type_hint="openapi",
                        detection_method="filename",
                        confidence="parser",
                    )
                )
            elif suffix == ".py" and _ROUTE_RE.search(text):
                detected.append(
                    DetectedInterfaceFile(
                        file_path=file_path,
                        interface_type_hint="python-route",
                        detection_method="ast-pattern",
                        confidence="analyser",
                    )
                )
            elif suffix in {".ts", ".tsx", ".js", ".jsx"} and _CLIENT_RE.search(text):
                detected.append(
                    DetectedInterfaceFile(
                        file_path=file_path,
                        interface_type_hint="http-client",
                        detection_method="client-pattern",
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
        server_records: list[InterfaceRecord] = []
        client_calls: list[tuple[str, str, str]] = []
        diagnostics: list[dict[str, str]] = []
        for detected in detect_result.detected_files:
            path = repo.root_path / detected.file_path
            if detected.interface_type_hint == "openapi":
                try:
                    for record in parse_openapi_file(
                        path,
                        repo_id=repo.repo_id,
                        snapshot_id=snapshot.snapshot_id,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                    ):
                        record.definition_files[0] = detected.file_path
                        server_records.append(record)
                except ValueError as exc:
                    diagnostics.append(
                        {"code": "OPENAPI_PARSE_FAILED", "message": str(exc)}
                    )
            elif detected.interface_type_hint == "python-route":
                server_records.extend(
                    _python_route_records(
                        path,
                        detected.file_path,
                        repo.repo_id,
                        snapshot.snapshot_id,
                        self.plugin_id,
                        self.plugin_version,
                    )
                )
            elif detected.interface_type_hint == "http-client":
                client_calls.extend(_client_calls(path, detected.file_path))
        records = _attach_clients(server_records, client_calls)
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
            route_node = interface_node(
                record, repo, snapshot, GraphNodeType.http_route
            )
            nodes.append(route_node)
            for op in record.operations:
                handlers = await _node_ids_for_file(
                    workspace,
                    repo.repo_id,
                    record.definition_files[0],
                    prefer_code=True,
                )
                op.server_handler_node_ids[:] = handlers[:1]
                for handler_id in op.server_handler_node_ids:
                    edges.append(
                        interface_edge(
                            repo,
                            snapshot,
                            GraphEdgeType.exposes,
                            handler_id,
                            route_node.node_id,
                            plugin_id=self.plugin_id,
                            plugin_version=self.plugin_version,
                            interface_id=record.interface_id,
                            operation_name=op.name,
                            confidence=op.confidence,
                        )
                    )
                for call_path in op.client_callsite_node_ids:
                    client_nodes = await _node_ids_for_file(
                        workspace, repo.repo_id, call_path, prefer_code=False
                    )
                    op.client_callsite_node_ids[:] = client_nodes[:1]
                    for client_id in op.client_callsite_node_ids:
                        edges.append(
                            interface_edge(
                                repo,
                                snapshot,
                                GraphEdgeType.consumes,
                                client_id,
                                route_node.node_id,
                                plugin_id=self.plugin_id,
                                plugin_version=self.plugin_version,
                                interface_id=record.interface_id,
                                operation_name=op.name,
                                confidence=op.confidence,
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
                operation_name=(
                    edge.properties.get("operation_name")
                    if isinstance(edge.properties.get("operation_name"), str)
                    else None
                ),
                direction=direction,
            )
            for edge in graph_slice.edges
        ]


_ROUTE_RE = re.compile(
    r"@(?:\w+\.)?(?P<method>get|post|put|delete|patch)\(['\"](?P<path>[^'\"]+)",
    re.I,
)
_FLASK_RE = re.compile(r"@(?:\w+\.)?route\(['\"](?P<path>[^'\"]+)")
_DJANGO_RE = re.compile(r"path\(['\"](?P<path>[^'\"]+)")
_CLIENT_RE = re.compile(
    r"(?:fetch|axios\.(?:get|post|put|delete|patch))\(\s*['\"`](?P<url>[^'\"`]+)",
    re.I,
)


def _read_text(path: Path) -> str:
    return path.read_text(errors="replace") if path.exists() else ""


def _python_route_records(
    path: Path,
    rel_path: str,
    repo_id: str,
    snapshot_id: str,
    plugin_id: str,
    plugin_version: str,
) -> list[InterfaceRecord]:
    text = _read_text(path)
    records: list[InterfaceRecord] = []
    matches = [*_ROUTE_RE.finditer(text), *_FLASK_RE.finditer(text)]
    if path.name == "urls.py":
        matches.extend(_DJANGO_RE.finditer(text))
    for match in matches:
        method = match.groupdict().get("method") or "GET"
        canonical = normalize_url_path(match.group("path"))
        name = f"{method.upper()} {canonical}"
        interface_id = make_interface_id(plugin_id, InterfaceKind.http, name, repo_id)
        operation = InterfaceOperation(
            operation_id=make_operation_id(interface_id, canonical, method.upper()),
            interface_id=interface_id,
            name=canonical,
            operation_type=OperationType.route,
            http_method=method.upper(),
            path_pattern=canonical,
            confidence="analyser",
            binding_method="framework-route",
        )
        records.append(
            InterfaceRecord(
                interface_id=interface_id,
                kind=InterfaceKind.http,
                plugin_id=plugin_id,
                plugin_version=plugin_version,
                interface_name=name,
                definition_files=[rel_path],
                source_repos=[repo_id],
                operations=[operation],
                confidence="analyser",
                snapshot_ids={repo_id: snapshot_id},
            )
        )
    return records


def _client_calls(path: Path, rel_path: str) -> list[tuple[str, str, str]]:
    return [
        (rel_path, normalize_url_path(match.group("url")), "analyser")
        for match in _CLIENT_RE.finditer(_read_text(path))
    ]


def _attach_clients(
    records: list[InterfaceRecord], client_calls: list[tuple[str, str, str]]
) -> list[InterfaceRecord]:
    for record in records:
        op = record.operations[0]
        for rel_path, url, confidence in client_calls:
            match_confidence = match_paths(op.path_pattern or op.name, url)
            if match_confidence:
                op.client_callsite_node_ids.append(rel_path)
                if confidence == "heuristic" or match_confidence == "heuristic":
                    op.confidence = "heuristic"
    return records


async def _node_ids_for_file(
    workspace: WorkspaceStore, repo_id: str, file_path: str, *, prefer_code: bool
) -> list[str]:
    graph_slice = await workspace.queries.fetch_by_file(repo_id, file_path)
    code_types = {GraphNodeType.function, GraphNodeType.method, GraphNodeType.class_}
    code_nodes = [n.node_id for n in graph_slice.nodes if n.node_type in code_types]
    if prefer_code and code_nodes:
        return code_nodes
    return [n.node_id for n in graph_slice.nodes]


def _graph_direction(direction: TraversalDirection) -> str:
    if direction == TraversalDirection.outbound:
        return "out"
    if direction == TraversalDirection.inbound:
        return "in"
    return "both"
