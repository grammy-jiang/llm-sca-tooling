"""Repository intelligence graph contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from llm_sca_tooling.schemas.base import JsonObject, SCHEMA_VERSION, StrictBaseModel, id_field, validate_confidence, validate_repo_relative_path
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, GraphEdgeType, GraphNodeType, Severity
from llm_sca_tooling.schemas.provenance import ArtifactRef, Provenance, RepoRef, SnapshotRef, SourceSpan

CODE_SYMBOL_TYPES = {
    GraphNodeType.CLASS,
    GraphNodeType.FUNCTION,
    GraphNodeType.METHOD,
    GraphNodeType.VARIABLE,
    GraphNodeType.TYPE,
    GraphNodeType.INTERFACE,
}


class GraphNode(StrictBaseModel):
    schema_version: str = SCHEMA_VERSION
    node_id: str = id_field("Stable graph node identifier.")
    node_type: GraphNodeType
    label: str = Field(min_length=1)
    qualified_name: str | None = None
    repo: RepoRef
    snapshot: SnapshotRef
    file_path: str | None = None
    span: SourceSpan | None = None
    provenance: Provenance
    properties: JsonObject = Field(default_factory=dict)
    created_ts: str = Field(min_length=1)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str | None) -> str | None:
        return None if value is None else validate_repo_relative_path(value)

    @model_validator(mode="after")
    def validate_node(self) -> "GraphNode":
        if self.repo.repo_id != self.snapshot.repo_id:
            raise ValueError("node repo.repo_id must match snapshot.repo_id")
        if self.repo.repo_id != self.provenance.repo.repo_id:
            raise ValueError("node provenance repo must match node repo")
        if self.snapshot.repo_id != self.provenance.snapshot.repo_id:
            raise ValueError("node provenance snapshot must match node snapshot")
        if self.node_type in CODE_SYMBOL_TYPES and not (self.qualified_name or self.properties.get("local_name")):
            raise ValueError("code symbol nodes require qualified_name or properties.local_name")
        return self


class GraphEdge(StrictBaseModel):
    schema_version: str = SCHEMA_VERSION
    edge_id: str = id_field("Stable graph edge identifier.")
    edge_type: GraphEdgeType
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    repo: RepoRef
    snapshot: SnapshotRef
    provenance: Provenance
    confidence: float = Field(ge=0.0, le=1.0)
    properties: JsonObject = Field(default_factory=dict)
    created_ts: str = Field(min_length=1)

    @field_validator("confidence")
    @classmethod
    def validate_confidence_field(cls, value: float) -> float:
        return validate_confidence(value)

    @model_validator(mode="after")
    def validate_edge(self) -> "GraphEdge":
        if self.source_id == self.target_id:
            raise ValueError("graph edges cannot be self-edges in Phase 1")
        if self.repo.repo_id != self.snapshot.repo_id:
            raise ValueError("edge repo.repo_id must match snapshot.repo_id")
        if self.repo.repo_id != self.provenance.repo.repo_id:
            raise ValueError("edge provenance repo must match edge repo")
        return self


class GraphDiagnostic(StrictBaseModel):
    diagnostic_id: str = id_field("Stable diagnostic identifier.")
    severity: Severity
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    affected_node_ids: list[str] = Field(default_factory=list)
    affected_edge_ids: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


ENDPOINT_RULES: dict[GraphEdgeType, tuple[set[GraphNodeType], set[GraphNodeType]]] = {
    GraphEdgeType.IMPORTS: (
        {GraphNodeType.FILE, GraphNodeType.MODULE, GraphNodeType.PACKAGE},
        {GraphNodeType.FILE, GraphNodeType.MODULE, GraphNodeType.PACKAGE},
    ),
    GraphEdgeType.CALLS: (
        {GraphNodeType.FUNCTION, GraphNodeType.METHOD},
        {GraphNodeType.FUNCTION, GraphNodeType.METHOD},
    ),
    GraphEdgeType.TESTS: (
        {GraphNodeType.TEST, GraphNodeType.GENERATED_TEST},
        {GraphNodeType.FUNCTION, GraphNodeType.METHOD, GraphNodeType.CLASS, GraphNodeType.HTTP_ROUTE, GraphNodeType.WEBSOCKET_EVENT},
    ),
    GraphEdgeType.USED_TOOL: (
        {GraphNodeType.RUN_RECORD, GraphNodeType.RUN_EVENT, GraphNodeType.SESSION},
        {GraphNodeType.TOOL_CALL},
    ),
}


class GraphDocument(StrictBaseModel):
    schema_family: Literal["graph"] = "graph"
    schema_version: str = SCHEMA_VERSION
    graph_id: str = id_field("Stable graph document identifier.")
    repo: RepoRef
    snapshot: SnapshotRef
    generated_by: str = Field(min_length=1)
    generated_ts: str = Field(min_length=1)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    diagnostics: list[GraphDiagnostic] = Field(default_factory=list)
    chunks: list[ArtifactRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_document(self) -> "GraphDocument":
        if self.repo.repo_id != self.snapshot.repo_id:
            raise ValueError("graph repo.repo_id must match snapshot.repo_id")
        validate_graph_document(self)
        return self


def validate_graph_document(document: GraphDocument) -> None:
    node_map = {node.node_id: node for node in document.nodes}
    if len(node_map) != len(document.nodes):
        raise ValueError("graph document contains duplicate node IDs")
    for edge in document.edges:
        if edge.source_id not in node_map or edge.target_id not in node_map:
            raise ValueError(f"edge {edge.edge_id} references a missing endpoint")
        validate_edge_endpoint_pair(edge, node_map[edge.source_id], node_map[edge.target_id])


def validate_edge_endpoint_pair(edge: GraphEdge, source: GraphNode, target: GraphNode) -> None:
    rule = ENDPOINT_RULES.get(edge.edge_type)
    if not rule:
        return
    valid_sources, valid_targets = rule
    if source.node_type not in valid_sources or target.node_type not in valid_targets:
        raise ValueError(f"invalid endpoint pairing for {edge.edge_type.value}")


def has_mixed_snapshots(document: GraphDocument) -> bool:
    snapshot_keys = {
        (node.snapshot.git_sha, node.snapshot.worktree_snapshot_id, node.snapshot.index_status)
        for node in document.nodes
    }
    snapshot_keys.update(
        (edge.snapshot.git_sha, edge.snapshot.worktree_snapshot_id, edge.snapshot.index_status)
        for edge in document.edges
    )
    return document.snapshot.index_status.value == "mixed" or len(snapshot_keys) > 1


graph_has_mixed_snapshots = has_mixed_snapshots


class RepositoryRecord(StrictBaseModel):
    repo_id: str = id_field("Stable repository identifier.")
    name: str | None = None
    root_ref: str | None = None
    default_branch: str | None = None
    registered_ts: str
    latest_snapshot: SnapshotRef | None = None
    capabilities: JsonObject = Field(default_factory=dict)
    metadata: JsonObject = Field(default_factory=dict)


class FileRecord(StrictBaseModel):
    node_id: str = id_field("File node identifier.")
    repo: RepoRef
    snapshot: SnapshotRef
    path: str
    language: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = None
    is_generated: bool | None = None
    is_test: bool | None = None
    is_vendor: bool | None = None
    encoding: str | None = None
    provenance: Provenance

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return validate_repo_relative_path(value)


class SymbolRecord(StrictBaseModel):
    node_id: str = id_field("Symbol node identifier.")
    symbol_type: GraphNodeType
    qualified_name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    file_path: str | None = None
    span: SourceSpan | None = None
    signature: str | None = None
    visibility: str | None = None
    language: str | None = None
    is_exported: bool | None = None
    is_generated: bool | None = None
    provenance: Provenance

    @field_validator("file_path")
    @classmethod
    def validate_symbol_file(cls, value: str | None) -> str | None:
        return None if value is None else validate_repo_relative_path(value)

    @model_validator(mode="after")
    def validate_location(self) -> "SymbolRecord":
        if self.provenance.derivation != DerivationType.ANALYSER and not (self.file_path and self.span):
            raise ValueError("symbols require file_path and span unless produced by an external analyser")
        return self


class InterfaceRecord(StrictBaseModel):
    interface_id: str = id_field("Interface identifier.")
    plugin_id: str = Field(min_length=1)
    interface_type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    producer_nodes: list[str] = Field(default_factory=list)
    consumer_nodes: list[str] = Field(default_factory=list)
    contract_refs: list[str] = Field(default_factory=list)
    schema_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    status: str = Field(min_length=1)
    provenance: Provenance
    attributes: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_interface(self) -> "InterfaceRecord":
        if self.provenance.derivation == DerivationType.LLM and self.provenance.evidence_strength != EvidenceStrength.SOFT_LLM:
            raise ValueError("LLM-derived interface records must be soft evidence")
        return self
