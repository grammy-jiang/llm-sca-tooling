"""Base contracts for interface plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import Field

from llm_sca_tooling.indexing.backends.base import BackendRunStats
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.plugins.capability import ConfidenceLevel, InterfaceKind, PluginAvailability, PluginCapabilityDescriptor, TraversalDirection
from llm_sca_tooling.plugins.interface_record import InterfaceRecord
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, validate_repo_relative_path
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import ArtifactRef, RepoRef, SnapshotRef
from llm_sca_tooling.storage.graph_store import GraphStore


class PluginConfig(StrictBaseModel):
    repo_root: Path
    run_id: str | None = None
    metadata: JsonObject = Field(default_factory=dict)
    model_config = StrictBaseModel.model_config | {"arbitrary_types_allowed": True}


class DetectedInterfaceFile(StrictBaseModel):
    file_path: str
    interface_type_hint: str
    detection_method: str
    confidence: ConfidenceLevel

    @classmethod
    def create(cls, file_path: str, interface_type_hint: str, detection_method: str, confidence: ConfidenceLevel) -> "DetectedInterfaceFile":
        return cls(file_path=validate_repo_relative_path(file_path), interface_type_hint=interface_type_hint, detection_method=detection_method, confidence=confidence)


class PluginDetectResult(StrictBaseModel):
    plugin_id: str
    repo_id: str
    snapshot_id: str
    detected_files: list[DetectedInterfaceFile] = Field(default_factory=list)
    detection_confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC
    diagnostics: list[IndexDiagnostic] = Field(default_factory=list)
    run_stats: BackendRunStats = Field(default_factory=BackendRunStats)


class PluginIndexResult(StrictBaseModel):
    plugin_id: str
    repo_id: str
    snapshot_id: str
    interface_records: list[InterfaceRecord] = Field(default_factory=list)
    generated_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    diagnostics: list[IndexDiagnostic] = Field(default_factory=list)
    run_stats: BackendRunStats = Field(default_factory=BackendRunStats)


class AmbiguousLinkRecord(StrictBaseModel):
    interface_id: str
    operation_name: str
    candidate_node_ids: list[str] = Field(default_factory=list)
    reason: str
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC


class PluginLinkResult(StrictBaseModel):
    plugin_id: str
    repo_id: str
    snapshot_id: str
    nodes_emitted: int = 0
    edges_emitted: int = 0
    interface_records_linked: int = 0
    ambiguous_links: list[AmbiguousLinkRecord] = Field(default_factory=list)
    diagnostics: list[IndexDiagnostic] = Field(default_factory=list)
    run_stats: BackendRunStats = Field(default_factory=BackendRunStats)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class TraversalLink(StrictBaseModel):
    from_node_id: str
    to_node_id: str
    via_interface_id: str
    plugin_id: str
    edge_type: str
    confidence: ConfidenceLevel
    operation_name: str | None = None
    direction: TraversalDirection
    from_repo_id: str | None = None
    to_repo_id: str | None = None
    from_language: str | None = None
    to_language: str | None = None


class InterfacePluginBase(ABC):
    plugin_id: str
    plugin_version: str
    interface_kind: InterfaceKind

    @abstractmethod
    def check_availability(self) -> PluginAvailability:
        raise NotImplementedError

    @abstractmethod
    def describe_capability(self) -> PluginCapabilityDescriptor:
        raise NotImplementedError

    @abstractmethod
    def detect(self, repo: RepoRef, snapshot: SnapshotRef, file_list: list[ScannedFile], config: PluginConfig) -> PluginDetectResult:
        raise NotImplementedError

    @abstractmethod
    def index(self, repo: RepoRef, snapshot: SnapshotRef, detect_result: PluginDetectResult, config: PluginConfig) -> PluginIndexResult:
        raise NotImplementedError

    @abstractmethod
    def link(self, repo: RepoRef, snapshot: SnapshotRef, index_result: PluginIndexResult, graph_store: GraphStore, config: PluginConfig) -> PluginLinkResult:
        raise NotImplementedError

    @abstractmethod
    def traverse(self, node_id: str, direction: TraversalDirection, graph_store: GraphStore) -> list[TraversalLink]:
        raise NotImplementedError
