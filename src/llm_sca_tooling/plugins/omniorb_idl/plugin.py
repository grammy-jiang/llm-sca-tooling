"""omniORB IDL interface plugin with a static fallback parser."""

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
    GeneratedArtifactRecord,
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

__all__ = ["OmniOrbIdlPlugin"]


class OmniOrbIdlPlugin(InterfacePluginBase):
    plugin_id = "omniorb-idl"
    plugin_version = "0.1.0"

    async def check_availability(self) -> PluginAvailability:
        return PluginAvailability(
            plugin_id=self.plugin_id,
            available=True,
            warnings=["omniidl optional; fallback tokenizer enabled"],
        )

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            interface_kinds=[InterfaceKind.idl],
            supported_server_languages=["cpp"],
            supported_client_languages=["python"],
            emitted_node_types=[GraphNodeType.idl_interface.value],
            emitted_edge_types=[
                GraphEdgeType.implements.value,
                GraphEdgeType.consumes.value,
                GraphEdgeType.ffi.value,
            ],
            max_confidence="heuristic",
        )

    async def detect(
        self, repo: RepositoryRecord, snapshot: SnapshotRecord, file_list: list[str]
    ) -> PluginDetectResult:
        detected = [
            DetectedInterfaceFile(
                file_path=file_path,
                interface_type_hint="idl",
                detection_method="extension",
                confidence="heuristic",
            )
            for file_path in file_list
            if file_path.endswith(".idl")
        ]
        return PluginDetectResult(
            plugin_id=self.plugin_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot.snapshot_id,
            detected_files=detected,
        )

    async def index(
        self,
        repo: RepositoryRecord,
        snapshot: SnapshotRecord,
        detect_result: PluginDetectResult,
        config: PluginConfig,
    ) -> PluginIndexResult:
        records = []
        for detected in detect_result.detected_files:
            text = (repo.root_path / detected.file_path).read_text(errors="replace")
            for match in _INTERFACE_RE.finditer(text):
                name = match.group("name")
                body = match.group("body")
                interface_id = make_interface_id(
                    self.plugin_id, InterfaceKind.idl, name, repo.repo_id
                )
                ops = [
                    InterfaceOperation(
                        operation_id=make_operation_id(interface_id, method, "IDL"),
                        interface_id=interface_id,
                        name=method,
                        operation_type=OperationType.method,
                        confidence="heuristic",
                        binding_method="idl-tokenizer",
                    )
                    for method in _METHOD_RE.findall(body)
                ]
                generated = [
                    GeneratedArtifactRecord(
                        artifact_id=f"gen:{interface_id}:{path}",
                        source_interface_id=interface_id,
                        generator_tool="omniidl",
                        file_paths=[path],
                        regeneration_command=f"omniidl {detected.file_path}",
                    )
                    for path in _generated_files(repo, name)
                ]
                records.append(
                    InterfaceRecord(
                        interface_id=interface_id,
                        kind=InterfaceKind.idl,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_name=name,
                        definition_files=[detected.file_path],
                        source_repos=[repo.repo_id],
                        operations=ops,
                        generated_artifacts=generated,
                        confidence="heuristic",
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
            idl_node = interface_node(
                record, repo, snapshot, GraphNodeType.idl_interface
            )
            nodes.append(idl_node)
            servant_nodes = await _nodes_matching(
                workspace, repo.repo_id, f"POA_{record.interface_name}"
            )
            caller_nodes = await _nodes_matching(
                workspace, repo.repo_id, record.interface_name
            )
            for node_id in servant_nodes[:1]:
                edges.append(
                    interface_edge(
                        repo,
                        snapshot,
                        GraphEdgeType.implements,
                        node_id,
                        idl_node.node_id,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_id=record.interface_id,
                        confidence=record.confidence,
                    )
                )
            for node_id in caller_nodes[:1]:
                edges.append(
                    interface_edge(
                        repo,
                        snapshot,
                        GraphEdgeType.consumes,
                        node_id,
                        idl_node.node_id,
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
        self, node_id: str, direction: TraversalDirection, workspace: WorkspaceStore
    ) -> list[TraversalLink]:
        graph_slice = await workspace.queries.fetch_neighbours(
            node_id,
            direction="both",
            edge_types=[
                GraphEdgeType.implements.value,
                GraphEdgeType.consumes.value,
                GraphEdgeType.ffi.value,
            ],
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


_INTERFACE_RE = re.compile(r"interface\s+(?P<name>\w+)\s*\{(?P<body>.*?)\};", re.S)
_METHOD_RE = re.compile(r"\b\w+\s+(\w+)\s*\([^)]*\)\s*;")


def _generated_files(repo: RepositoryRecord, name: str) -> list[str]:
    needles = {
        f"{name}SK.cc".lower(),
        f"{name}_idl.py".lower(),
        f"{name}_skel.cc".lower(),
    }
    return [
        path.relative_to(repo.root_path).as_posix()
        for path in repo.root_path.rglob("*")
        if path.name.lower() in needles
    ]


async def _nodes_matching(
    workspace: WorkspaceStore, repo_id: str, text: str
) -> list[str]:
    nodes = []
    for node_type in [
        GraphNodeType.class_.value,
        GraphNodeType.function.value,
        GraphNodeType.module.value,
    ]:
        nodes.extend(await workspace.queries.fetch_nodes_by_type(repo_id, node_type))
    return [
        node.node_id
        for node in nodes
        if text in (node.qualified_name or "") or text in node.label
    ]
