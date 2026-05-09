"""omniORB IDL plugin orchestration."""

from __future__ import annotations

from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.plugins.base import (
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
    GeneratedArtifactRecord,
    InterfaceOperation,
    InterfaceRecord,
    interface_id_for,
    operation_id_for,
)
from llm_sca_tooling.plugins.omniorb_idl.caller_finder import find_python_callers
from llm_sca_tooling.plugins.omniorb_idl.cpp_servant_linker import find_cpp_servants
from llm_sca_tooling.plugins.omniorb_idl.generated_artifact_tracker import (
    generated_artifacts,
)
from llm_sca_tooling.plugins.omniorb_idl.idl_parser import parse_idl
from llm_sca_tooling.plugins.omniorb_idl.python_stub_linker import find_python_stubs
from llm_sca_tooling.plugins.traverse_edges import traverse_interface_edges
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.graph_store import GraphStore


class OmniOrbIdlPlugin(InterfacePluginBase):
    plugin_id = "omniorb-idl"
    plugin_version = "0.1.0"
    interface_kind = InterfaceKind.IDL

    def check_availability(self) -> PluginAvailability:
        return PluginAvailability(
            plugin_id=self.plugin_id,
            available=True,
            warnings=["omniidl optional; fallback tokenizer enabled"],
        )

    def describe_capability(self) -> PluginCapabilityDescriptor:
        return PluginCapabilityDescriptor(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            interface_kinds=[InterfaceKind.IDL],
            supported_server_languages=["cpp"],
            supported_client_languages=["python"],
            emitted_node_types=[
                GraphNodeType.IDL_INTERFACE,
                GraphNodeType.FUNCTION,
                GraphNodeType.CLASS,
            ],
            emitted_edge_types=[
                GraphEdgeType.IMPLEMENTS,
                GraphEdgeType.CONSUMES,
                GraphEdgeType.FFI,
            ],
            max_confidence=ConfidenceLevel.ANALYSER,
            requires_external_tools=["omniidl"],
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
            if file.path.endswith(".idl"):
                result.detected_files.append(
                    DetectedInterfaceFile.create(
                        file.path, "idl", "extension", ConfidenceLevel.PARSER
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
        for detected in detect_result.detected_files:
            path = config.repo_root / detected.file_path
            for interface in parse_idl(path.read_text(encoding="utf-8")):
                name = interface["name"]
                interface_id = interface_id_for(
                    self.plugin_id, InterfaceKind.IDL, name, repo.repo_id
                )
                operations = [
                    InterfaceOperation(
                        operation_id=operation_id_for(
                            interface_id, method["name"], "IDL"
                        ),
                        interface_id=interface_id,
                        name=method["name"],
                        operation_type=OperationType.METHOD,
                        parameters=[
                            {
                                "name": p["name"],
                                "location": p["direction"],
                                "schema": {"type": p["type"]},
                                "required": True,
                                "nullable": False,
                            }
                            for p in method["parameters"]
                        ],
                        confidence=ConfidenceLevel.HEURISTIC,
                        binding_method="idl_tokenizer",
                        metadata={"return_type": method["return_type"]},
                    )
                    for method in interface["methods"]
                ]
                artifacts = [
                    GeneratedArtifactRecord(
                        artifact_id=f"generated:{interface_id}:{i}",
                        source_interface_id=interface_id,
                        generator_tool="omniidl",
                        file_paths=[file_path],
                        is_checked_in=True,
                        regeneration_command=f"omniidl {detected.file_path}",
                        provenance=provenance,
                    )
                    for i, file_path in enumerate(
                        generated_artifacts(config.repo_root, name)
                    )
                ]
                result.interface_records.append(
                    InterfaceRecord(
                        interface_id=interface_id,
                        kind=InterfaceKind.IDL,
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        interface_name=name,
                        definition_files=[detected.file_path],
                        source_repos=[repo.repo_id],
                        operations=operations,
                        generated_artifacts=artifacts,
                        confidence=ConfidenceLevel.HEURISTIC,
                        snapshot_ids={repo.repo_id: detect_result.snapshot_id},
                        provenance=provenance,
                    )
                )
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
            idl_node = plugin_node(
                repo,
                snapshot,
                plugin_id=self.plugin_id,
                plugin_version=self.plugin_version,
                node_type=GraphNodeType.IDL_INTERFACE,
                key=record.interface_name,
                label=record.interface_name,
                interface_id=record.interface_id,
                file_path=record.definition_files[0],
                confidence=record.confidence,
                properties={
                    "generated_artifacts": [
                        artifact.file_paths for artifact in record.generated_artifacts
                    ]
                },
                run_id=config.run_id,
            )
            graph_store.upsert_node(idl_node)
            result.nodes.append(idl_node)
            servants = find_cpp_servants(config.repo_root, record.interface_name)
            stubs = find_python_stubs(config.repo_root, record.interface_name)
            callers = find_python_callers(
                config.repo_root,
                [stub["module_name"] for stub in stubs],
                [op.name for op in record.operations],
            )
            for servant in servants:
                servant_node = find_symbol_by_name(
                    graph_store,
                    repo.repo_id,
                    servant["file_path"],
                    servant["class_name"],
                ) or synthetic_symbol(
                    repo,
                    snapshot,
                    servant["file_path"],
                    servant["class_name"],
                    servant["line"],
                    "cpp",
                    self.plugin_id,
                    self.plugin_version,
                    config.run_id,
                )
                graph_store.upsert_node(servant_node)
                result.nodes.append(servant_node)
                edge = plugin_edge(
                    repo,
                    snapshot,
                    plugin_id=self.plugin_id,
                    plugin_version=self.plugin_version,
                    edge_type=GraphEdgeType.IMPLEMENTS,
                    source_id=servant_node.node_id,
                    target_id=idl_node.node_id,
                    interface_id=record.interface_id,
                    confidence=ConfidenceLevel.ANALYSER,
                    run_id=config.run_id,
                )
                graph_store.upsert_edge(edge)
                result.edges.append(edge)
            for stub in stubs:
                stub_node = synthetic_symbol(
                    repo,
                    snapshot,
                    stub["file_path"],
                    stub["module_name"],
                    stub["line"],
                    "python",
                    self.plugin_id,
                    self.plugin_version,
                    config.run_id,
                )
                stub_node.properties["generated"] = True
                stub_node.properties["generator_tool"] = "omniidl"
                graph_store.upsert_node(stub_node)
                result.nodes.append(stub_node)
                edge = plugin_edge(
                    repo,
                    snapshot,
                    plugin_id=self.plugin_id,
                    plugin_version=self.plugin_version,
                    edge_type=GraphEdgeType.FFI,
                    source_id=stub_node.node_id,
                    target_id=idl_node.node_id,
                    interface_id=record.interface_id,
                    confidence=ConfidenceLevel.ANALYSER,
                    run_id=config.run_id,
                )
                graph_store.upsert_edge(edge)
                result.edges.append(edge)
            for caller in callers:
                caller_node = synthetic_symbol(
                    repo,
                    snapshot,
                    caller["file_path"],
                    caller["function"],
                    caller["line"],
                    "python",
                    self.plugin_id,
                    self.plugin_version,
                    config.run_id,
                )
                graph_store.upsert_node(caller_node)
                result.nodes.append(caller_node)
                edge = plugin_edge(
                    repo,
                    snapshot,
                    plugin_id=self.plugin_id,
                    plugin_version=self.plugin_version,
                    edge_type=GraphEdgeType.CONSUMES,
                    source_id=caller_node.node_id,
                    target_id=idl_node.node_id,
                    interface_id=record.interface_id,
                    operation_name=caller["method"],
                    confidence=ConfidenceLevel.ANALYSER,
                    run_id=config.run_id,
                )
                graph_store.upsert_edge(edge)
                result.edges.append(edge)
        result.nodes_emitted = len(result.nodes)
        result.edges_emitted = len(result.edges)
        result.interface_records_linked = len(index_result.interface_records)
        return result

    def traverse(
        self, node_id: str, direction: TraversalDirection, graph_store: GraphStore
    ) -> list[TraversalLink]:
        return traverse_interface_edges(self.plugin_id, node_id, direction, graph_store)
