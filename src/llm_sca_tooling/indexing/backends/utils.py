"""Shared backend graph builders."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.scanner import ScannedFile, edge_id, node_id
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef, SourceSpan
from llm_sca_tooling.storage.workspace import _now_ts


def backend_node(repo: RepoRef, snapshot: SnapshotRef, backend_id: str, file: ScannedFile, node_type: GraphNodeType, qname: str, label: str, *, line: int = 1, end_line: int | None = None, run_id: str | None = None, derivation: DerivationType = DerivationType.PARSER, evidence_strength: EvidenceStrength = EvidenceStrength.HARD_STATIC, confidence: float = 0.8, extra: dict | None = None) -> GraphNode:
    span = SourceSpan(file_path=file.path, start_line=line, end_line=end_line or line)
    provenance = make_provenance(
        source_tool=backend_id,
        repo=repo,
        snapshot=snapshot,
        source_run_id=run_id,
        file=file.path,
        span=span,
        derivation=derivation,
        evidence_strength=evidence_strength,
        confidence=confidence,
        attributes={"backend_id": backend_id, "backend_version": "0.1.0"},
    )
    return GraphNode(
        node_id=node_id(repo.repo_id, snapshot, node_type, f"{backend_id}:{qname}:{line}"),
        node_type=node_type,
        label=label,
        qualified_name=qname,
        repo=repo,
        snapshot=snapshot,
        file_path=file.path,
        span=span,
        provenance=provenance,
        properties={"backend_id": backend_id, "language": file.language, **(extra or {})},
        created_ts=_now_ts(),
    )


def backend_edge(repo: RepoRef, snapshot: SnapshotRef, backend_id: str, edge_type: GraphEdgeType, source_id: str, target_id: str, *, run_id: str | None = None, derivation: DerivationType = DerivationType.PARSER, evidence_strength: EvidenceStrength = EvidenceStrength.HARD_STATIC, confidence: float = 0.8, extra: dict | None = None) -> GraphEdge:
    provenance = make_provenance(
        source_tool=backend_id,
        repo=repo,
        snapshot=snapshot,
        source_run_id=run_id,
        derivation=derivation,
        evidence_strength=evidence_strength,
        confidence=confidence,
        attributes={"backend_id": backend_id, "backend_version": "0.1.0"},
    )
    return GraphEdge(
        edge_id=edge_id(repo.repo_id, snapshot, edge_type, source_id, target_id) if not extra or "edge_key" not in extra else edge_id(repo.repo_id, snapshot, edge_type, source_id, target_id + str(extra["edge_key"])),
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        repo=repo,
        snapshot=snapshot,
        provenance=provenance,
        confidence=confidence,
        properties={"backend_id": backend_id, **(extra or {})},
        created_ts=_now_ts(),
    )


def line_no_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1
