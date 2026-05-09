"""Helpers for plugin graph facts."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.hashing import hash_text
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.scanner import node_id, edge_id
from llm_sca_tooling.plugins.capability import CONFIDENCE_VALUE, ConfidenceLevel
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef, SourceSpan
from llm_sca_tooling.storage.graph_store import GraphStore
from llm_sca_tooling.storage.workspace import _now_ts


def plugin_node(
    repo: RepoRef,
    snapshot: SnapshotRef,
    *,
    plugin_id: str,
    plugin_version: str,
    node_type: GraphNodeType,
    key: str,
    label: str,
    interface_id: str,
    file_path: str | None = None,
    line: int | None = None,
    confidence: ConfidenceLevel = ConfidenceLevel.ANALYSER,
    properties: dict | None = None,
    run_id: str | None = None,
) -> GraphNode:
    span = SourceSpan(file_path=file_path, start_line=line or 1, end_line=line or 1) if file_path else None
    provenance = make_provenance(
        source_tool=plugin_id,
        repo=repo,
        snapshot=snapshot,
        source_run_id=run_id,
        file=file_path,
        span=span,
        derivation=_derivation(confidence),
        evidence_strength=EvidenceStrength.STRUCTURED_REPOSITORY,
        confidence=CONFIDENCE_VALUE[confidence],
        attributes={"plugin_id": plugin_id, "plugin_version": plugin_version, "interface_id": interface_id},
    )
    return GraphNode(
        node_id=node_id(repo.repo_id, snapshot, node_type, f"{plugin_id}:{key}"),
        node_type=node_type,
        label=label,
        qualified_name=key,
        repo=repo,
        snapshot=snapshot,
        file_path=file_path,
        span=span,
        provenance=provenance,
        properties={"plugin_id": plugin_id, "plugin_version": plugin_version, "interface_id": interface_id, **(properties or {})},
        created_ts=_now_ts(),
    )


def plugin_edge(
    repo: RepoRef,
    snapshot: SnapshotRef,
    *,
    plugin_id: str,
    plugin_version: str,
    edge_type: GraphEdgeType,
    source_id: str,
    target_id: str,
    interface_id: str,
    operation_name: str | None = None,
    confidence: ConfidenceLevel = ConfidenceLevel.ANALYSER,
    properties: dict | None = None,
    run_id: str | None = None,
) -> GraphEdge:
    provenance = make_provenance(
        source_tool=plugin_id,
        repo=repo,
        snapshot=snapshot,
        source_run_id=run_id,
        derivation=_derivation(confidence),
        evidence_strength=EvidenceStrength.STRUCTURED_REPOSITORY,
        confidence=CONFIDENCE_VALUE[confidence],
        attributes={"plugin_id": plugin_id, "plugin_version": plugin_version, "interface_id": interface_id},
    )
    key = target_id if operation_name is None else f"{target_id}:{operation_name}"
    return GraphEdge(
        edge_id=edge_id(repo.repo_id, snapshot, edge_type, source_id, key),
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        repo=repo,
        snapshot=snapshot,
        provenance=provenance,
        confidence=CONFIDENCE_VALUE[confidence],
        properties={"plugin_id": plugin_id, "plugin_version": plugin_version, "interface_id": interface_id, "operation_name": operation_name, "confidence": confidence.value, **(properties or {})},
        created_ts=_now_ts(),
    )


def find_symbol_by_name(graph_store: GraphStore, repo_id: str, file_path: str, name: str) -> GraphNode | None:
    rows = graph_store.conn.execute(
        "SELECT payload_json FROM graph_nodes WHERE repo_id=? AND file_path=? AND node_type IN ('function','method','class','module')",
        (repo_id, file_path),
    ).fetchall()
    for row in rows:
        node = GraphNode.model_validate_json(row["payload_json"])
        if node.label == name or (node.qualified_name or "").endswith(f":{name}") or (node.qualified_name or "").endswith(f".{name}"):
            return node
    return None


def synthetic_symbol(repo: RepoRef, snapshot: SnapshotRef, file_path: str, name: str, line: int, language: str, plugin_id: str, plugin_version: str, run_id: str | None = None) -> GraphNode:
    return plugin_node(
        repo,
        snapshot,
        plugin_id=plugin_id,
        plugin_version=plugin_version,
        node_type=GraphNodeType.FUNCTION,
        key=f"{file_path}:{name}:{line}",
        label=name,
        interface_id=f"synthetic:{hash_text(file_path + name, length=16)}",
        file_path=file_path,
        line=line,
        confidence=ConfidenceLevel.HEURISTIC,
        properties={"language": language, "synthetic": True},
        run_id=run_id,
    )


def relative_files(repo_root: Path, suffixes: tuple[str, ...]) -> list[str]:
    return [path.relative_to(repo_root).as_posix() for path in repo_root.rglob("*") if path.is_file() and path.suffix in suffixes]


def _derivation(confidence: ConfidenceLevel) -> DerivationType:
    if confidence == ConfidenceLevel.PARSER:
        return DerivationType.PARSER
    if confidence == ConfidenceLevel.ANALYSER:
        return DerivationType.ANALYSER
    return DerivationType.HEURISTIC
