"""Workspace store initialization and component wiring."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection

from llm_sca_tooling.schemas.base import SCHEMA_VERSION, StrictBaseModel
from llm_sca_tooling.storage.errors import WorkspaceNotFoundError
from llm_sca_tooling.storage.migrations import STORAGE_VERSION, apply_migrations
from llm_sca_tooling.storage.sqlite import connect
from llm_sca_tooling.storage.transactions import transaction


def _now_ts() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class WorkspaceStatus(StrictBaseModel):
    workspace_id: str
    storage_version: str
    schema_versions: dict[str, str]
    storage_root: str
    artifact_root: str
    last_migration: str | None


class WorkspaceStore:
    def __init__(self, storage_root: Path, conn: Connection) -> None:
        self.storage_root = storage_root
        self.db_path = storage_root / "workspace.db"
        self.artifact_root = storage_root / "artifacts"
        self.export_root = storage_root / "exports"
        self.lock_root = storage_root / "locks"
        self.conn = conn
        from llm_sca_tooling.sarif.store import SarifRunStore
        from llm_sca_tooling.storage.artifacts import ArtifactStore
        from llm_sca_tooling.storage.export_import import ImportExportService
        from llm_sca_tooling.storage.graph_store import GraphStore
        from llm_sca_tooling.storage.harness_store import HarnessMetadataStore
        from llm_sca_tooling.storage.operations import OperationalStore
        from llm_sca_tooling.storage.registry import RepositoryRegistry
        from llm_sca_tooling.storage.snapshots import SnapshotStore

        self.repositories = RepositoryRegistry(conn)
        self.snapshots = SnapshotStore(conn)
        self.artifacts = ArtifactStore(conn)
        self.graph = GraphStore(conn, self.snapshots)
        self.harness = HarnessMetadataStore(conn)
        self.operations = OperationalStore(conn)
        self.exports = ImportExportService(self)
        self.sarif = SarifRunStore(conn)

    @contextmanager
    def transaction(self, reason: str = "storage") -> Iterator[None]:
        with transaction(self.conn, reason):
            yield

    def close(self) -> None:
        self.conn.close()

    def workspace_status(self) -> WorkspaceStatus:
        metadata = {
            row["key"]: json.loads(row["value_json"])
            for row in self.conn.execute(
                "SELECT key, value_json FROM workspace_metadata"
            )
        }
        last_migration = self.conn.execute(
            "SELECT max(version) AS version FROM schema_migrations"
        ).fetchone()["version"]
        return WorkspaceStatus(
            workspace_id=metadata["workspace_id"],
            storage_version=metadata["storage_version"],
            schema_versions=metadata["schema_versions"],
            storage_root=str(self.storage_root),
            artifact_root=metadata["artifact_root"],
            last_migration=last_migration,
        )


def _put_metadata(conn: Connection, key: str, value: object) -> None:
    conn.execute(
        """
        INSERT INTO workspace_metadata(key, value_json, updated_ts)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_ts=excluded.updated_ts
        """,
        (key, json.dumps(value, sort_keys=True), _now_ts()),
    )


def initialize_workspace(path: str | Path, *, create: bool = True) -> WorkspaceStore:
    storage_root = Path(path).expanduser().resolve()
    if not storage_root.exists():
        if not create:
            raise WorkspaceNotFoundError(f"workspace does not exist: {storage_root}")
        storage_root.mkdir(parents=True)
    for child in ("artifacts", "exports", "locks"):
        (storage_root / child).mkdir(exist_ok=True)
    db_path = storage_root / "workspace.db"
    conn = connect(db_path)
    apply_migrations(conn)
    existing = conn.execute(
        "SELECT value_json FROM workspace_metadata WHERE key='workspace_id'"
    ).fetchone()
    if existing is None:
        _put_metadata(conn, "workspace_id", f"workspace:{uuid.uuid4().hex}")
        _put_metadata(conn, "created_ts", _now_ts())
    _put_metadata(conn, "storage_version", STORAGE_VERSION)
    _put_metadata(conn, "schema_versions", {"phase1": SCHEMA_VERSION})
    _put_metadata(conn, "artifact_root", str(storage_root / "artifacts"))
    _put_metadata(conn, "default_redaction_policy", {"status": "redacted"})
    last_migration = conn.execute(
        "SELECT max(version) AS version FROM schema_migrations"
    ).fetchone()["version"]
    _put_metadata(conn, "last_migration", last_migration)
    conn.commit()
    return WorkspaceStore(storage_root, conn)


def open_workspace(path: str | Path) -> WorkspaceStore:
    storage_root = Path(path).expanduser().resolve()
    if not (storage_root / "workspace.db").exists():
        raise WorkspaceNotFoundError(
            f"workspace database does not exist: {storage_root / 'workspace.db'}"
        )
    conn = connect(storage_root / "workspace.db")
    apply_migrations(conn)
    return WorkspaceStore(storage_root, conn)
