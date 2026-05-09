"""Graph query result contracts."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel
from llm_sca_tooling.schemas.enums import SnapshotConsistency
from llm_sca_tooling.schemas.graph import GraphDiagnostic, GraphEdge, GraphNode


class GraphSlice(StrictBaseModel):
    repo_id: str
    requested_snapshot_id: str | None = None
    snapshot_ids: list[str]
    snapshot_consistency: SnapshotConsistency
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    diagnostics: list[GraphDiagnostic] = Field(default_factory=list)
    truncated: bool = False
    limit: int | None = None
    provenance_summary: JsonObject = Field(default_factory=dict)


class GraphStoreStatus(StrictBaseModel):
    repo_id: str
    snapshot_id: str | None
    node_count: int
    edge_count: int
    snapshot_consistency: SnapshotConsistency
