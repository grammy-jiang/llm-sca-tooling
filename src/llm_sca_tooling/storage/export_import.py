"""Basic graph and run export/import service."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Literal

from pydantic import Field

from llm_sca_tooling.schemas.base import (
    SCHEMA_VERSION,
    JsonObject,
    StrictBaseModel,
)
from llm_sca_tooling.schemas.enums import RedactionStatus
from llm_sca_tooling.schemas.graph import GraphDocument
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.storage.errors import ImportExportError
from llm_sca_tooling.storage.ids import payload_hash
from llm_sca_tooling.storage.registry import RegisteredRepository
from llm_sca_tooling.storage.workspace import WorkspaceStore, _now_ts


class ExportBundle(StrictBaseModel):
    export_id: str
    export_type: str
    created_ts: str
    schema_versions: dict[str, str]
    storage_version: str
    repos: list[JsonObject] = Field(default_factory=list)
    snapshots: list[JsonObject] = Field(default_factory=list)
    payload: JsonObject
    payload_hash: str
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    redaction_policy: JsonObject = Field(default_factory=dict)
    diagnostics: list[JsonObject] = Field(default_factory=list)


class BundleValidationResult(StrictBaseModel):
    valid: bool
    diagnostics: list[str] = Field(default_factory=list)


class ImportResult(StrictBaseModel):
    inserted_repos: int = 0
    inserted_snapshots: int = 0
    inserted_nodes: int = 0
    inserted_edges: int = 0


class ImportExportService:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def export_graph(
        self,
        repo_id: str,
        snapshot_id: str,
        destination: str | Path,
        *,
        include_artifacts: bool = False,
    ) -> ExportBundle:
        repo = self.workspace.repositories.get_repo(repo_id)
        snapshot = self.workspace.snapshots.get_snapshot(snapshot_id)
        nodes = [
            self.workspace.graph.fetch_node(row["node_id"])
            for row in self.workspace.conn.execute(
                "SELECT node_id FROM graph_nodes WHERE repo_id=? AND snapshot_id=?",
                (repo_id, snapshot_id),
            )
        ]
        edges = [
            self.workspace.graph.fetch_edge(row["edge_id"])
            for row in self.workspace.conn.execute(
                "SELECT edge_id FROM graph_edges WHERE repo_id=? AND snapshot_id=?",
                (repo_id, snapshot_id),
            )
        ]
        nodes = [node for node in nodes if node is not None]
        edges = [edge for edge in edges if edge is not None]
        document = GraphDocument(
            graph_id=f"graph:{repo_id}:{snapshot_id}",
            repo=repo_to_ref(repo),
            snapshot=snapshot.snapshot,
            generated_by="llm_sca_tooling.storage",
            generated_ts=_now_ts(),
            nodes=nodes,
            edges=edges,
            diagnostics=[],
            chunks=[],
        )
        payload = {"graph_document": document.model_dump(mode="json")}
        bundle = self._bundle(
            "graph_snapshot",
            payload,
            repos=[repo.public_metadata()],
            snapshots=[snapshot.model_dump(mode="json")],
        )
        self._write_bundle(bundle, destination)
        return bundle

    def export_run(
        self, run_id: str, destination: str | Path, *, include_artifacts: bool = False
    ) -> ExportBundle:
        view = self.workspace.operations.get_run(run_id, include_events=True)
        payload = {
            "run": view.run.model_dump(mode="json"),
            "events": [event.model_dump(mode="json") for event in view.events],
        }
        bundle = self._bundle("run_record", payload)
        self._write_bundle(bundle, destination)
        return bundle

    def export_workspace_summary(self, destination: str | Path) -> ExportBundle:
        payload = {
            "workspace": self.workspace.workspace_status().model_dump(mode="json")
        }
        repos = [
            repo.public_metadata()
            for repo in self.workspace.repositories.list_repos(active_only=False)
        ]
        bundle = self._bundle("workspace_metadata", payload, repos=repos)
        self._write_bundle(bundle, destination)
        return bundle

    def validate_bundle(self, path: str | Path) -> BundleValidationResult:
        try:
            bundle = self._read_bundle(path)
            if bundle.schema_versions.get("phase1") != SCHEMA_VERSION:
                return BundleValidationResult(
                    valid=False, diagnostics=["incompatible Phase 1 schema version"]
                )
            if bundle.payload_hash != payload_hash(bundle.payload):
                return BundleValidationResult(
                    valid=False, diagnostics=["payload hash mismatch"]
                )
        except Exception as exc:
            return BundleValidationResult(valid=False, diagnostics=[str(exc)])
        return BundleValidationResult(valid=True)

    def import_bundle(
        self,
        path: str | Path,
        *,
        mode: Literal["validate_then_insert"] = "validate_then_insert",
    ) -> ImportResult:
        validation = self.validate_bundle(path)
        if not validation.valid:
            raise ImportExportError("; ".join(validation.diagnostics))
        bundle = self._read_bundle(path)
        if bundle.export_type != "graph_snapshot":
            raise ImportExportError(f"unsupported import type: {bundle.export_type}")
        document = GraphDocument.model_validate(bundle.payload["graph_document"])
        with self.workspace.transaction("import graph bundle"):
            repo = repo_to_import_row(
                bundle.repos[0]
                if bundle.repos
                else {
                    "repo_id": document.repo.repo_id,
                    "name": document.repo.name or document.repo.repo_id,
                }
            )
            self.workspace.conn.execute(
                """
                INSERT OR IGNORE INTO repositories(
                  repo_id, name, root_path, root_path_hash, vcs_type,
                  registered_ts, last_seen_ts, active, index_status,
                  capabilities_json, metadata_json)
                VALUES (?, ?, ?, ?, 'imported', ?, ?, 1, 'unknown', '{}', '{}')
                """,
                (
                    repo["repo_id"],
                    repo["name"],
                    repo["root_path"],
                    repo["root_path_hash"],
                    _now_ts(),
                    _now_ts(),
                ),
            )
            self.workspace.snapshots.record_snapshot(document.snapshot)
            for node in document.nodes:
                self.workspace.graph._add_node_no_commit(node, upsert=False)
            for edge in document.edges:
                self.workspace.graph._add_edge_no_commit(edge, upsert=False)
        return ImportResult(
            inserted_repos=1,
            inserted_snapshots=1,
            inserted_nodes=len(document.nodes),
            inserted_edges=len(document.edges),
        )

    def export_graph_slice(
        self,
        nodes: list[object],
        edges: list[object],
        destination: str | Path,
        *,
        repo_id: str,
        snapshot_id: str | None = None,
    ) -> ExportBundle:
        """Export an arbitrary graph slice (subset of nodes+edges)."""
        from llm_sca_tooling.schemas.enums import IndexStatus
        from llm_sca_tooling.schemas.provenance import SnapshotRef

        if snapshot_id:
            try:
                snapshot_ref = self.workspace.snapshots.get_snapshot(
                    snapshot_id
                ).snapshot
            except Exception:
                snapshot_ref = None
        else:
            snapshot_ref = None

        if snapshot_ref is None and nodes:
            first = nodes[0]
            snapshot_ref = getattr(first, "snapshot", None)
        if snapshot_ref is None:
            snapshot_ref = SnapshotRef(
                repo_id=repo_id,
                dirty=False,
                index_status=IndexStatus.UNKNOWN,
                captured_ts=_now_ts(),
            )

        repo_ref = self._repo_ref(repo_id)
        document = GraphDocument(
            graph_id=f"slice:{repo_id}:{snapshot_id or 'any'}",
            repo=repo_ref,
            snapshot=snapshot_ref,
            generated_by="llm_sca_tooling.storage",
            generated_ts=_now_ts(),
            nodes=nodes,
            edges=edges,
            diagnostics=[],
            chunks=[],
        )
        payload = {"graph_slice": document.model_dump(mode="json")}
        bundle = self._bundle("graph_slice", payload)
        self._write_bundle(bundle, destination)
        return bundle

    def export_repo_registry(self, destination: str | Path) -> ExportBundle:
        """Export the full repository registry."""
        repos = self.workspace.repositories.list_repos(active_only=False)
        payload = {"repos": [r.public_metadata() for r in repos]}
        bundle = self._bundle(
            "repo_registry", payload, repos=[r.public_metadata() for r in repos]
        )
        self._write_bundle(bundle, destination)
        return bundle

    def export_operational_bundle(
        self,
        destination: str | Path,
        *,
        repo_id: str | None = None,
    ) -> ExportBundle:
        """Export operational records and incidents."""
        records = self.workspace.operations.query_operational_records(repo_id=repo_id)
        incidents = self.workspace.operations.query_incidents(repo_id=repo_id)
        payload = {
            "operational_records": [r.model_dump(mode="json") for r in records],
            "incidents": [i.model_dump(mode="json") for i in incidents],
        }
        bundle = self._bundle("operational_bundle", payload)
        self._write_bundle(bundle, destination)
        return bundle

    def export_readiness_bundle(
        self,
        destination: str | Path,
        *,
        run_id: str | None = None,
    ) -> ExportBundle:
        """Export harness readiness and condition sheets."""
        sql = "SELECT payload_json FROM readiness_reports ORDER BY created_ts DESC"
        params: tuple[object, ...] = ()
        if run_id:
            sql = (
                "SELECT payload_json FROM harness_conditions"
                " WHERE run_id=? ORDER BY captured_ts DESC"
            )
            params = (run_id,)
        rows = self.workspace.conn.execute(sql, params).fetchall()
        payload = {"harness_records": [json.loads(r["payload_json"]) for r in rows]}
        bundle = self._bundle("readiness_bundle", payload)
        self._write_bundle(bundle, destination)
        return bundle

    def export_incident_bundle(
        self,
        destination: str | Path,
        *,
        repo_id: str | None = None,
        status: str | None = None,
    ) -> ExportBundle:
        """Export incidents with their linked run events."""
        from llm_sca_tooling.schemas.incidents import IncidentStatus

        incidents = self.workspace.operations.query_incidents(
            repo_id=repo_id,
            status=IncidentStatus(status) if status else None,
        )
        payload = {"incidents": [i.model_dump(mode="json") for i in incidents]}
        bundle = self._bundle("incident_bundle", payload)
        self._write_bundle(bundle, destination)
        return bundle

    def _repo_ref(self, repo_id: str) -> object:
        from llm_sca_tooling.schemas.provenance import RepoRef

        try:
            repo = self.workspace.repositories.get_repo(repo_id)
            return repo_to_ref(repo)
        except Exception:
            return RepoRef(
                repo_id=repo_id,
                name=repo_id,
                root_ref=None,
                remote_url_hash=None,
                default_branch=None,
            )

    def _bundle(
        self,
        export_type: str,
        payload: JsonObject,
        *,
        repos: list[JsonObject] | None = None,
        snapshots: list[JsonObject] | None = None,
    ) -> ExportBundle:
        return ExportBundle(
            export_id=f"export:{uuid.uuid4().hex}",
            export_type=export_type,
            created_ts=_now_ts(),
            schema_versions={"phase1": SCHEMA_VERSION},
            storage_version="0.1.0",
            repos=repos or [],
            snapshots=snapshots or [],
            payload=payload,
            payload_hash=payload_hash(payload),
            redaction_policy={"default": RedactionStatus.REDACTED.value},
        )

    def _write_bundle(self, bundle: ExportBundle, destination: str | Path) -> None:
        path = Path(destination)
        path.mkdir(parents=True, exist_ok=True)
        (path / "export.json").write_text(
            json.dumps(bundle.model_dump(mode="json"), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def _read_bundle(self, path: str | Path) -> ExportBundle:
        bundle_path = Path(path)
        if bundle_path.is_dir():
            bundle_path = bundle_path / "export.json"
        return ExportBundle.model_validate_json(bundle_path.read_text(encoding="utf-8"))


def repo_to_ref(repo: RegisteredRepository) -> object:
    from llm_sca_tooling.schemas.provenance import RepoRef

    return RepoRef(
        repo_id=repo.repo_id,
        name=repo.name,
        root_ref=None,
        remote_url_hash=repo.remote_url_hash,
        default_branch=repo.default_branch,
    )


def repo_to_import_row(metadata: JsonObject) -> JsonObject:
    repo_id = str(metadata["repo_id"])
    return {
        "repo_id": repo_id,
        "name": str(metadata.get("name") or repo_id),
        "root_path": f"imported://{repo_id}",
        "root_path_hash": str(metadata.get("root_path_hash") or payload_hash(metadata)),
    }
