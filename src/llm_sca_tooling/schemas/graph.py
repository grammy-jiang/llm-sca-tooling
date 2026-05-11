"""Graph node, edge, and document models.

The checked-in ``schemas/graph.schema.json`` is the cross-language contract
for all future indexing backends, interface plugins, SARIF binders, workflow
outputs, memory records, and evaluation facts.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import (
    SCHEMA_VERSION,
    JsonValue,
    NonEmptyStr,
    StrictModel,
)
from llm_sca_tooling.schemas.provenance import (
    ArtifactRef,
    Provenance,
    RepoRef,
    SnapshotRef,
    SourceSpan,
)

__all__ = [
    "GraphNodeType",
    "GraphEdgeType",
    "GraphDiagnosticSeverity",
    "GraphNode",
    "GraphEdge",
    "GraphDiagnostic",
    "GraphDocument",
    "RepositoryRecord",
    "FileRecord",
    "SymbolRecord",
    "InterfaceRecord",
    "VALID_EDGE_ENDPOINTS",
]


# ---------------------------------------------------------------------------
# Node type enum
# ---------------------------------------------------------------------------


class GraphNodeType(str, Enum):
    # Repository structure
    repo = "repo"
    package = "package"
    directory = "directory"
    file = "file"
    module = "module"
    # Code symbols
    class_ = "class"
    function = "function"
    method = "method"
    variable = "variable"
    type_ = "type"
    interface = "interface"
    # Interface boundaries
    idl_interface = "idl_interface"
    http_route = "http_route"
    websocket_event = "websocket_event"
    grpc_service = "grpc_service"
    protobuf_message = "protobuf_message"
    # Specification and contracts
    document = "document"
    design_clause = "design_clause"
    intent_node = "intent_node"
    contract_artifact = "contract_artifact"
    generated_test = "generated_test"
    predicate = "predicate"
    # Evidence
    test = "test"
    runtime_trace = "runtime_trace"
    sast_rule = "sast_rule"
    sarif_alert = "sarif_alert"
    build_target = "build_target"
    ci_job = "ci_job"
    eval_run = "eval_run"
    # Change and review
    patch = "patch"
    diff_hunk = "diff_hunk"
    risk_finding = "risk_finding"
    verdict = "verdict"
    # Memory
    trajectory = "trajectory"
    issue_class = "issue_class"
    fl_decision = "fl_decision"
    patch_class = "patch_class"
    outcome = "outcome"
    # Operational harness
    session = "session"
    run_record = "run_record"
    run_event = "run_event"
    harness_condition = "harness_condition"
    permission_profile = "permission_profile"
    tool_policy = "tool_policy"
    tool_call = "tool_call"
    approval = "approval"
    budget_event = "budget_event"
    compaction_event = "compaction_event"
    monitor_alert = "monitor_alert"
    incident = "incident"
    readiness_score = "readiness_score"
    maintainability_oracle = "maintainability_oracle"
    manifest_regression = "manifest_regression"


# ---------------------------------------------------------------------------
# Edge type enum
# ---------------------------------------------------------------------------


class GraphEdgeType(str, Enum):
    # Code and evidence
    contains = "contains"
    imports = "imports"
    calls = "calls"
    dataflow = "dataflow"
    tests = "tests"
    documents = "documents"
    decomposes_to = "decomposes_to"
    checks = "checks"
    satisfies = "satisfies"
    violates = "violates"
    implements = "implements"
    exposes = "exposes"
    consumes = "consumes"
    ffi = "ffi"
    nullable = "nullable"
    owns = "owns"
    instantiates = "instantiates"
    warned_by = "warned_by"
    fixed_by = "fixed_by"
    changed_by = "changed_by"
    observed_in = "observed_in"
    # Operational
    used_tool = "used_tool"
    approved_by = "approved_by"
    denied_by = "denied_by"
    verified_by = "verified_by"
    blocked_by = "blocked_by"
    compacted_to = "compacted_to"
    promoted_to = "promoted_to"
    triggered_incident = "triggered_incident"


# ---------------------------------------------------------------------------
# Endpoint compatibility matrix (conservative initial set)
# ---------------------------------------------------------------------------

_STRUCTURAL = {
    GraphNodeType.repo,
    GraphNodeType.package,
    GraphNodeType.directory,
    GraphNodeType.file,
    GraphNodeType.module,
}
_CODE_SYMBOLS = {
    GraphNodeType.class_,
    GraphNodeType.function,
    GraphNodeType.method,
    GraphNodeType.variable,
    GraphNodeType.type_,
}
_INTERFACES = {
    GraphNodeType.interface,
    GraphNodeType.idl_interface,
    GraphNodeType.http_route,
    GraphNodeType.websocket_event,
    GraphNodeType.grpc_service,
    GraphNodeType.protobuf_message,
}
_EVIDENCE = {
    GraphNodeType.test,
    GraphNodeType.runtime_trace,
    GraphNodeType.sast_rule,
    GraphNodeType.sarif_alert,
    GraphNodeType.build_target,
    GraphNodeType.ci_job,
}
_CONTRACT = {
    GraphNodeType.document,
    GraphNodeType.design_clause,
    GraphNodeType.intent_node,
    GraphNodeType.contract_artifact,
    GraphNodeType.generated_test,
    GraphNodeType.predicate,
}
_ALL_NODES = set(GraphNodeType)

VALID_EDGE_ENDPOINTS: dict[
    GraphEdgeType, tuple[frozenset[GraphNodeType], frozenset[GraphNodeType]]
] = {
    GraphEdgeType.contains: (
        frozenset(_STRUCTURAL | _CODE_SYMBOLS),
        frozenset(_ALL_NODES - {GraphNodeType.repo}),
    ),
    GraphEdgeType.imports: (
        frozenset({GraphNodeType.file, GraphNodeType.module, GraphNodeType.package}),
        frozenset({GraphNodeType.file, GraphNodeType.module, GraphNodeType.package}),
    ),
    GraphEdgeType.calls: (
        frozenset({GraphNodeType.function, GraphNodeType.method}),
        frozenset({GraphNodeType.function, GraphNodeType.method}),
    ),
    GraphEdgeType.tests: (
        frozenset({GraphNodeType.test, GraphNodeType.generated_test}),
        frozenset(_CODE_SYMBOLS | _INTERFACES),
    ),
    GraphEdgeType.warned_by: (
        frozenset(_CODE_SYMBOLS | {GraphNodeType.file} | _INTERFACES),
        frozenset({GraphNodeType.sarif_alert, GraphNodeType.sast_rule}),
    ),
    GraphEdgeType.changed_by: (
        frozenset(_ALL_NODES - {GraphNodeType.patch, GraphNodeType.diff_hunk}),
        frozenset({GraphNodeType.patch, GraphNodeType.diff_hunk}),
    ),
    GraphEdgeType.triggered_incident: (
        frozenset({GraphNodeType.monitor_alert, GraphNodeType.run_event}),
        frozenset({GraphNodeType.incident}),
    ),
}


def check_edge_endpoints(
    edge_type: GraphEdgeType,
    source_type: GraphNodeType,
    target_type: GraphNodeType,
) -> str | None:
    """Return an error message if the endpoint pair is invalid, else None."""
    if edge_type not in VALID_EDGE_ENDPOINTS:
        return None  # unknown edge type → not checked yet
    valid_sources, valid_targets = VALID_EDGE_ENDPOINTS[edge_type]
    if source_type not in valid_sources:
        return (
            f"edge {edge_type.value!r} does not allow source type {source_type.value!r}"
        )
    if target_type not in valid_targets:
        return (
            f"edge {edge_type.value!r} does not allow target type {target_type.value!r}"
        )
    return None


# ---------------------------------------------------------------------------
# Graph models
# ---------------------------------------------------------------------------


class GraphDiagnosticSeverity(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"


class GraphDiagnostic(StrictModel):
    diagnostic_id: NonEmptyStr
    severity: GraphDiagnosticSeverity
    code: NonEmptyStr
    message: str
    affected_node_ids: list[str] = Field(default_factory=list)
    affected_edge_ids: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


class GraphNode(StrictModel):
    schema_version: str = SCHEMA_VERSION
    node_id: NonEmptyStr
    node_type: GraphNodeType
    label: str
    qualified_name: str | None = None
    repo: RepoRef
    snapshot: SnapshotRef
    file_path: str | None = None
    span: SourceSpan | None = None
    provenance: Provenance
    properties: dict[str, JsonValue] = Field(default_factory=dict)
    created_ts: NonEmptyStr

    @model_validator(mode="after")
    def _repo_id_consistency(self) -> GraphNode:
        if self.repo.repo_id != self.snapshot.repo_id:
            raise ValueError("repo.repo_id must match snapshot.repo_id")
        return self


class GraphEdge(StrictModel):
    schema_version: str = SCHEMA_VERSION
    edge_id: NonEmptyStr
    edge_type: GraphEdgeType
    source_id: NonEmptyStr
    target_id: NonEmptyStr
    repo: RepoRef
    snapshot: SnapshotRef
    provenance: Provenance
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0
    properties: dict[str, JsonValue] = Field(default_factory=dict)
    created_ts: NonEmptyStr

    @model_validator(mode="after")
    def _self_loop_guard(self) -> GraphEdge:
        if self.source_id == self.target_id:
            raise ValueError(
                f"edge {self.edge_id!r}: source_id and target_id must differ"
            )
        return self

    @model_validator(mode="after")
    def _repo_id_consistency(self) -> GraphEdge:
        if self.repo.repo_id != self.snapshot.repo_id:
            raise ValueError("repo.repo_id must match snapshot.repo_id")
        return self


class GraphDocument(StrictModel):
    """A complete or partial graph over a repository snapshot."""

    schema_family: str = "graph"
    schema_version: str = SCHEMA_VERSION
    graph_id: NonEmptyStr
    repo: RepoRef
    snapshot: SnapshotRef
    generated_by: NonEmptyStr
    generated_ts: NonEmptyStr
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    diagnostics: list[GraphDiagnostic] = Field(default_factory=list)
    chunks: list[ArtifactRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _repo_id_consistency(self) -> GraphDocument:
        if self.repo.repo_id != self.snapshot.repo_id:
            raise ValueError("repo.repo_id must match snapshot.repo_id")
        return self

    def has_mixed_snapshots(self) -> bool:
        """Return True if any node or edge references a different snapshot."""
        base_sha = self.snapshot.git_sha
        return any(n.snapshot.git_sha != base_sha for n in self.nodes) or any(
            e.snapshot.git_sha != base_sha for e in self.edges
        )


# ---------------------------------------------------------------------------
# Typed helper models for repository, file, symbol, and interface records
# ---------------------------------------------------------------------------


class RepositoryRecord(StrictModel):
    repo_id: NonEmptyStr
    name: str
    root_ref: str | None = None
    default_branch: str | None = None
    registered_ts: NonEmptyStr
    latest_snapshot: SnapshotRef | None = None
    capabilities: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class FileRecord(StrictModel):
    node_id: NonEmptyStr
    repo: RepoRef
    snapshot: SnapshotRef
    path: NonEmptyStr
    language: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    is_generated: bool = False
    is_test: bool = False
    is_vendor: bool = False
    encoding: str | None = None
    provenance: Provenance


class SymbolRecord(StrictModel):
    node_id: NonEmptyStr
    symbol_type: GraphNodeType
    qualified_name: str
    display_name: str
    file_path: NonEmptyStr
    span: SourceSpan | None = None
    signature: str | None = None
    visibility: str | None = None
    language: str | None = None
    is_exported: bool = False
    is_generated: bool = False
    provenance: Provenance


class InterfaceType(str, Enum):
    http_rest = "http_rest"
    websocket = "websocket"
    idl = "idl"
    grpc = "grpc"
    protobuf = "protobuf"
    ffi = "ffi"
    other = "other"


class InterfaceRecord(StrictModel):
    interface_id: NonEmptyStr
    plugin_id: str | None = None
    interface_type: InterfaceType
    name: str
    producer_nodes: list[str] = Field(default_factory=list)
    consumer_nodes: list[str] = Field(default_factory=list)
    contract_refs: list[str] = Field(default_factory=list)
    schema_refs: list[str] = Field(default_factory=list)
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0
    status: str = "active"
    provenance: Provenance
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
