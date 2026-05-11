"""Helpers for writing interface graph facts."""

from __future__ import annotations

from datetime import UTC, datetime

from llm_sca_tooling.indexing.hashing import make_edge_id, make_node_id
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.plugins.interface_record import InterfaceRecord
from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    RepoRef,
    SnapshotRef,
)
from llm_sca_tooling.storage.registry import RepositoryRecord
from llm_sca_tooling.storage.snapshots import SnapshotRecord

__all__ = ["interface_edge", "interface_node", "repo_ref", "snapshot_ref"]


def repo_ref(repo: RepositoryRecord) -> RepoRef:
    return RepoRef(repo_id=repo.repo_id, name=repo.name)


def snapshot_ref(snapshot: SnapshotRecord) -> SnapshotRef:
    return SnapshotRef(
        repo_id=snapshot.repo_id,
        git_sha=snapshot.git_sha,
        branch=snapshot.branch,
        dirty=snapshot.dirty,
        worktree_snapshot_id=snapshot.worktree_snapshot_id,
        index_status=snapshot.index_status,
        captured_ts=snapshot.captured_ts,
    )


def interface_node(
    record: InterfaceRecord,
    repo: RepositoryRecord,
    snapshot: SnapshotRecord,
    node_type: GraphNodeType,
) -> GraphNode:
    repo_model = repo_ref(repo)
    snap_model = snapshot_ref(snapshot)
    return GraphNode(
        node_id=make_node_id(repo.repo_id, node_type.value, record.interface_id),
        node_type=node_type,
        label=record.interface_name,
        qualified_name=f"{record.plugin_id}:{record.interface_name}",
        repo=repo_model,
        snapshot=snap_model,
        file_path=record.definition_files[0] if record.definition_files else None,
        provenance=make_provenance(
            repo_model,
            snap_model,
            source_tool=f"llm-sca-tooling.plugin.{record.plugin_id}",
            source_version=record.plugin_version,
            derivation=DerivationType.analyser,
            evidence_strength=EvidenceStrength.structured_repository,
            confidence=_confidence(record.confidence),
        ),
        properties=record.model_dump(mode="json"),
        created_ts=_now(),
    )


def interface_edge(
    repo: RepositoryRecord,
    snapshot: SnapshotRecord,
    edge_type: GraphEdgeType,
    source_id: str,
    target_id: str,
    *,
    plugin_id: str,
    plugin_version: str,
    interface_id: str,
    operation_name: str | None = None,
    confidence: str = "heuristic",
) -> GraphEdge:
    repo_model = repo_ref(repo)
    snap_model = snapshot_ref(snapshot)
    return GraphEdge(
        edge_id=make_edge_id(repo.repo_id, edge_type.value, source_id, target_id),
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        repo=repo_model,
        snapshot=snap_model,
        provenance=make_provenance(
            repo_model,
            snap_model,
            source_tool=f"llm-sca-tooling.plugin.{plugin_id}",
            source_version=plugin_version,
            derivation=DerivationType.analyser,
            evidence_strength=EvidenceStrength.structured_repository,
            confidence=_confidence(confidence),
        ),
        confidence=_confidence(confidence),
        properties={
            "plugin_id": plugin_id,
            "plugin_version": plugin_version,
            "interface_id": interface_id,
            "operation_name": operation_name,
            "binding_confidence": confidence,
        },
        created_ts=_now(),
    )


def _confidence(value: str) -> float:
    return {"parser": 0.95, "analyser": 0.8, "heuristic": 0.45}.get(value, 0.3)


def _now() -> str:
    return datetime.now(UTC).isoformat()
