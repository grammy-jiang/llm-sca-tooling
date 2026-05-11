"""SQLModel ORM table definitions for the Phase 2 local store.

All table classes must be imported once before ``SQLModel.metadata.create_all()``
is called.  The ``__init__.py`` imports this module at package load time.
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

__all__ = [
    "WorkspaceMetadataRow",
    "RepositoryRow",
    "SnapshotRow",
    "GraphNodeRow",
    "GraphEdgeRow",
    "GraphDiagnosticRow",
    "GraphManifestRow",
    "HarnessMetadataRow",
    "SupplyChainRow",
    "RunRecordRow",
    "RunRepositoryRow",
    "RunEventRow",
    "HarnessConditionRow",
    "OperationalRecordRow",
    "IncidentRow",
    "IncidentRunRow",
    "IncidentEventRow",
    "PromotionRecordRow",
    "ReadinessReportRow",
    "ArtifactRow",
    "SchemaMigrationRow",
]


class WorkspaceMetadataRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "workspace_metadata"  # type: ignore[assignment]

    key: str = Field(primary_key=True)
    value_json: str
    updated_ts: str


class RepositoryRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "repositories"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.UniqueConstraint("root_path", name="uq_repositories_root_path"),
        sa.Index("idx_repositories_active", "active"),
        sa.Index("idx_repositories_name", "name"),
        sa.Index("idx_repositories_latest_snapshot", "latest_snapshot_id"),
    )

    repo_id: str = Field(primary_key=True)
    name: str
    root_path: str
    root_path_hash: str
    vcs_type: str = "git"
    remote_url_hash: str | None = None
    default_branch: str | None = None
    current_branch: str | None = None
    registered_ts: str
    last_seen_ts: str
    active: int = 1
    index_status: str = "not_indexed"
    latest_snapshot_id: str | None = None
    capabilities_json: str = "{}"
    metadata_json: str = "{}"


class SnapshotRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "snapshots"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.Index("idx_snapshots_repo", "repo_id"),
        sa.Index("idx_snapshots_git_sha", "repo_id", "git_sha"),
        sa.Index("idx_snapshots_worktree", "repo_id", "worktree_snapshot_id"),
        sa.Index("idx_snapshots_status", "repo_id", "index_status"),
        sa.Index("idx_snapshots_captured_ts", "captured_ts"),
    )

    snapshot_id: str = Field(primary_key=True)
    repo_id: str = Field(foreign_key="repositories.repo_id")
    git_sha: str | None = None
    branch: str | None = None
    dirty: int = 0
    worktree_snapshot_id: str | None = None
    index_status: str = "unknown"
    captured_ts: str
    source_run_id: str | None = None
    source_event_id: str | None = None
    file_state_hash: str | None = None
    diagnostics_json: str = "[]"
    metadata_json: str = "{}"


class GraphNodeRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "graph_nodes"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.Index("idx_graph_nodes_repo_snapshot", "repo_id", "snapshot_id"),
        sa.Index("idx_graph_nodes_type", "repo_id", "node_type"),
        sa.Index("idx_graph_nodes_file", "repo_id", "snapshot_id", "file_path"),
        sa.Index("idx_graph_nodes_qualified_name", "repo_id", "qualified_name"),
        sa.Index(
            "idx_graph_nodes_span", "repo_id", "file_path", "start_line", "end_line"
        ),
        sa.Index("idx_graph_nodes_derivation", "derivation"),
    )

    node_id: str = Field(primary_key=True)
    repo_id: str = Field(foreign_key="repositories.repo_id")
    snapshot_id: str = Field(description="snapshot reference (git_sha or worktree_id)")
    node_type: str
    label: str
    qualified_name: str | None = None
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    confidence: float = 1.0
    derivation: str
    evidence_strength: str
    provenance_hash: str
    payload_json: str
    created_ts: str
    updated_ts: str


class GraphEdgeRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "graph_edges"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.Index("idx_graph_edges_repo_snapshot", "repo_id", "snapshot_id"),
        sa.Index("idx_graph_edges_type", "repo_id", "edge_type"),
        sa.Index("idx_graph_edges_source", "source_id"),
        sa.Index("idx_graph_edges_target", "target_id"),
        sa.Index("idx_graph_edges_source_type", "source_id", "edge_type"),
        sa.Index("idx_graph_edges_target_type", "target_id", "edge_type"),
    )

    edge_id: str = Field(primary_key=True)
    repo_id: str = Field(foreign_key="repositories.repo_id")
    snapshot_id: str = Field(description="snapshot reference (git_sha or worktree_id)")
    edge_type: str
    source_id: str = Field(foreign_key="graph_nodes.node_id")
    target_id: str = Field(foreign_key="graph_nodes.node_id")
    confidence: float = 1.0
    derivation: str
    evidence_strength: str
    provenance_hash: str
    payload_json: str
    created_ts: str
    updated_ts: str


class GraphDiagnosticRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "graph_diagnostics"  # type: ignore[assignment]

    diagnostic_id: str = Field(primary_key=True)
    repo_id: str = Field(foreign_key="repositories.repo_id")
    snapshot_id: str | None = None
    severity: str
    code: str
    message: str
    affected_node_ids_json: str = "[]"
    affected_edge_ids_json: str = "[]"
    provenance_json: str | None = None
    created_ts: str


class GraphManifestRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "graph_manifests"  # type: ignore[assignment]

    graph_id: str = Field(primary_key=True)
    repo_id: str = Field(foreign_key="repositories.repo_id")
    snapshot_id: str = Field(description="snapshot reference (git_sha or worktree_id)")
    node_count: int = 0
    edge_count: int = 0
    chunk_artifact_ids_json: str = "[]"
    schema_version: str = "0.1.0"
    generated_ts: str
    payload_json: str = "{}"


class HarnessMetadataRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "harness_metadata"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.Index("idx_harness_metadata_repo_kind", "repo_id", "kind"),
        sa.Index("idx_harness_metadata_active", "active"),
    )

    metadata_id: str = Field(primary_key=True)
    repo_id: str | None = Field(default=None, foreign_key="repositories.repo_id")
    kind: str
    active: int = 1
    payload_json: str
    payload_hash: str
    created_ts: str
    updated_ts: str


class SupplyChainRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "supply_chain_records"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.Index("idx_supply_chain_repo", "repo_id"),
        sa.Index("idx_supply_chain_type", "component_type"),
    )

    supply_chain_record_id: str = Field(primary_key=True)
    repo_id: str | None = Field(default=None, foreign_key="repositories.repo_id")
    component_type: str
    name: str
    version: str | None = None
    source: str | None = None
    hash: str | None = None
    payload_json: str
    captured_ts: str


class RunRecordRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "run_records"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.Index("idx_run_records_workflow", "workflow"),
        sa.Index("idx_run_records_status", "status"),
        sa.Index("idx_run_records_start_ts", "start_ts"),
    )

    run_id: str = Field(primary_key=True)
    workflow: str
    user_intent_hash: str = ""
    status: str = "created"
    start_ts: str
    end_ts: str | None = None
    toolset_hash: str = "unknown"
    policy_id: str = "unknown"
    permission_profile: str = "read-only"
    harness_condition_id: str | None = None
    final_verdict_id: str | None = None
    run_event_count: int = 0
    redaction_policy_json: str = "{}"
    payload_json: str = "{}"
    created_ts: str
    updated_ts: str


class RunRepositoryRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "run_repositories"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.Index("idx_run_repositories_repo", "repo_id"),
    )

    run_id: str = Field(primary_key=True, foreign_key="run_records.run_id")
    repo_id: str = Field(primary_key=True, foreign_key="repositories.repo_id")


class RunEventRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "run_events"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.UniqueConstraint("run_id", "seq", name="uq_run_events_run_seq"),
        sa.Index("idx_run_events_run", "run_id", "seq"),
        sa.Index("idx_run_events_type", "type"),
        sa.Index("idx_run_events_stage", "stage"),
        sa.Index("idx_run_events_ts", "ts"),
        sa.Index("idx_run_events_policy_action", "policy_action"),
    )

    event_id: str = Field(primary_key=True)
    run_id: str = Field(foreign_key="run_records.run_id")
    seq: int
    ts: str
    type: str
    actor: str
    stage: str
    policy_action: str | None = None
    redaction_status: str
    token_count: int | None = None
    wall_ms: int | None = None
    payload_json: str = "{}"
    created_ts: str


class HarnessConditionRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "harness_conditions"  # type: ignore[assignment]

    harness_condition_id: str = Field(primary_key=True)
    run_id: str | None = Field(default=None, foreign_key="run_records.run_id")
    toolset_hash: str = "unknown"
    permission_profile: str = "read-only"
    captured_ts: str
    payload_json: str = "{}"


class OperationalRecordRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "operational_records"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.Index("idx_operational_records_repo", "repo_id"),
        sa.Index("idx_operational_records_run", "run_id"),
        sa.Index("idx_operational_records_kind", "kind"),
        sa.Index("idx_operational_records_incident", "incident_id"),
        sa.Index("idx_operational_records_created_ts", "created_ts"),
        sa.Index("idx_operational_records_policy_action", "policy_action"),
    )

    record_id: str = Field(primary_key=True)
    repo_id: str | None = Field(default=None, foreign_key="repositories.repo_id")
    run_id: str | None = Field(default=None, foreign_key="run_records.run_id")
    event_id: str | None = None
    kind: str
    status: str | None = None
    policy_action: str | None = None
    severity: str | None = None
    incident_id: str | None = None
    payload_json: str
    created_ts: str


class IncidentRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "incidents"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.Index("idx_incidents_status", "status"),
        sa.Index("idx_incidents_severity", "severity"),
        sa.Index("idx_incidents_repo", "primary_repo_id"),
    )

    incident_id: str = Field(primary_key=True)
    severity: str
    status: str = "open"
    title: str
    primary_repo_id: str | None = Field(
        default=None, foreign_key="repositories.repo_id"
    )
    opened_ts: str
    closed_ts: str | None = None
    payload_json: str


class IncidentRunRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "incident_runs"  # type: ignore[assignment]

    incident_id: str = Field(primary_key=True, foreign_key="incidents.incident_id")
    run_id: str = Field(primary_key=True, foreign_key="run_records.run_id")


class IncidentEventRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "incident_events"  # type: ignore[assignment]

    incident_id: str = Field(primary_key=True, foreign_key="incidents.incident_id")
    event_id: str = Field(primary_key=True)


class PromotionRecordRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "promotion_records"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.Index("idx_promotion_records_run", "source_run_id"),
        sa.Index("idx_promotion_records_state", "review_state"),
        sa.Index("idx_promotion_records_type", "target_type"),
    )

    promotion_id: str = Field(primary_key=True)
    source_run_id: str = Field(foreign_key="run_records.run_id")
    target_type: str
    review_state: str = "pending"
    owner: str | None = None
    expires_ts: str | None = None
    payload_json: str
    created_ts: str
    updated_ts: str


class ReadinessReportRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "readiness_reports"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.Index("idx_readiness_reports_repo", "repo_id", "created_ts"),
        sa.Index("idx_readiness_reports_stage", "stage"),
    )

    readiness_report_id: str = Field(primary_key=True)
    repo_id: str = Field(foreign_key="repositories.repo_id")
    stage: str
    total_score: int = 0
    threshold_status: str = "unknown"
    no_regression_status: str = "unknown"
    payload_json: str
    created_ts: str


class ArtifactRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "artifacts"  # type: ignore[assignment]
    __table_args__: ClassVar[tuple] = (  # type: ignore[assignment]
        sa.Index("idx_artifacts_repo", "repo_id"),
        sa.Index("idx_artifacts_run", "run_id"),
        sa.Index("idx_artifacts_kind", "kind"),
        sa.Index("idx_artifacts_sha256", "sha256"),
    )

    artifact_id: str = Field(primary_key=True)
    repo_id: str | None = Field(default=None, foreign_key="repositories.repo_id")
    run_id: str | None = Field(default=None, foreign_key="run_records.run_id")
    kind: str
    uri: str
    sha256: str | None = None
    size_bytes: int | None = None
    media_type: str | None = None
    redaction_status: str
    created_ts: str
    metadata_json: str = "{}"


class SchemaMigrationRow(SQLModel, table=True):
    __tablename__: ClassVar[str] = "schema_migrations"  # type: ignore[assignment]

    version: str = Field(primary_key=True)
    applied_ts: str
    checksum: str
    description: str
