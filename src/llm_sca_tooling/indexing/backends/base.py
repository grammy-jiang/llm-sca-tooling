"""Backend interfaces and result models."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import Field

from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import ArtifactRef


class BackendCapabilities(StrictBaseModel):
    backend_id: str
    installed: bool
    version: str
    supported_languages: list[str] = Field(default_factory=list)
    supported_node_types: list[str] = Field(default_factory=list)
    supported_edge_types: list[str] = Field(default_factory=list)
    requires_external_binary: bool = False
    known_limitations: list[str] = Field(default_factory=list)


class BackendAvailability(StrictBaseModel):
    backend_id: str
    available: bool
    tool_path: str | None = None
    tool_version: str | None = None
    missing_deps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BackendRunStats(StrictBaseModel):
    files_scanned: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    nodes_emitted: int = 0
    edges_emitted: int = 0
    diagnostics_emitted: int = 0
    wall_ms: int = 0
    peak_memory_mb: float | None = None


class BackendCapabilityDescriptor(StrictBaseModel):
    backend_id: str
    backend_version: str
    supported_node_types: list[GraphNodeType] = Field(default_factory=list)
    supported_edge_types: list[GraphEdgeType] = Field(default_factory=list)
    max_confidence: EvidenceStrength = EvidenceStrength.STRUCTURED_REPOSITORY
    derivation: DerivationType = DerivationType.PARSER
    can_resolve_cross_file_calls: bool = False
    can_resolve_cross_module_calls: bool = False
    can_produce_type_edges: bool = False
    can_produce_nullness_edges: bool = False
    can_produce_dataflow_edges: bool = False
    can_index_generated_files: bool = False
    requires_compile_commands: bool = False
    requires_build_artifacts: bool = False
    incremental_support: bool = False
    lsp_based: bool = False
    languages: list[str] = Field(default_factory=list)


class BackendResult(StrictBaseModel):
    backend_id: str
    backend_version: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    diagnostics: list[IndexDiagnostic] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    files_processed: list[str] = Field(default_factory=list)
    files_skipped: list[str] = Field(default_factory=list)
    started_ts: str
    ended_ts: str
    capabilities_used: list[str] = Field(default_factory=list)
    run_stats: BackendRunStats = Field(default_factory=BackendRunStats)
    output_hash: str | None = None


class BackendBase(ABC):
    backend_id: str

    @abstractmethod
    def backend_version(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def check_availability(self) -> BackendAvailability:
        raise NotImplementedError

    @abstractmethod
    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        raise NotImplementedError

    def supports_incremental(self) -> bool:
        return self.describe_capabilities().incremental_support
