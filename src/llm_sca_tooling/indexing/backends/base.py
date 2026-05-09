"""Backend interfaces and result models."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.schemas.base import StrictBaseModel
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
