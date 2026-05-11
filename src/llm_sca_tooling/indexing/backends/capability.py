"""Phase 5 backend capability and output contracts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal

import orjson

from llm_sca_tooling.indexing.backends.base import BackendResult
from llm_sca_tooling.indexing.diagnostics import IndexingDiagnostic
from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import DerivationType

__all__ = [
    "BackendAvailability",
    "BackendCapabilityDescriptor",
    "BackendOutput",
    "BackendRunStats",
    "SkippedFile",
]


@dataclass(frozen=True)
class BackendAvailability:
    backend_id: str
    available: bool
    tool_path: str | None = None
    tool_version: str | None = None
    missing_deps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BackendRunStats:
    files_scanned: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    nodes_emitted: int = 0
    edges_emitted: int = 0
    diagnostics_emitted: int = 0
    wall_ms: int = 0
    peak_memory_mb: float | None = None


@dataclass(frozen=True)
class SkippedFile:
    file_path: str
    reason: str


@dataclass(frozen=True)
class BackendCapabilityDescriptor:
    backend_id: str
    backend_version: str
    supported_node_types: list[GraphNodeType]
    supported_edge_types: list[GraphEdgeType]
    max_confidence: Literal["parser", "heuristic"]
    derivation: DerivationType
    can_resolve_cross_file_calls: bool
    can_resolve_cross_module_calls: bool
    can_produce_type_edges: bool
    can_produce_nullness_edges: bool
    can_produce_dataflow_edges: bool
    can_index_generated_files: bool
    requires_compile_commands: bool
    requires_build_artifacts: bool
    incremental_support: bool
    lsp_based: bool
    languages: list[str]


@dataclass
class BackendOutput:
    backend_id: str
    backend_version: str
    repo_id: str
    snapshot_id: str
    git_sha: str | None
    worktree_snapshot_id: str | None
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    diagnostics: list[IndexingDiagnostic] = field(default_factory=list)
    skipped_files: list[SkippedFile] = field(default_factory=list)
    capabilities_used: list[str] = field(default_factory=list)
    run_stats: BackendRunStats = field(default_factory=BackendRunStats)

    @property
    def output_hash(self) -> str:
        payload = {
            "backend_id": self.backend_id,
            "nodes": [n.node_id for n in self.nodes],
            "edges": [e.edge_id for e in self.edges],
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }
        return hashlib.sha256(
            orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
        ).hexdigest()

    def to_backend_result(self) -> BackendResult:
        result = BackendResult(self.backend_id, self.backend_version)
        result.nodes = self.nodes
        result.edges = self.edges
        result.diagnostics = self.diagnostics
        result.files_processed = self.run_stats.files_scanned
        result.files_skipped = self.run_stats.files_skipped
        result.finish()
        return result
