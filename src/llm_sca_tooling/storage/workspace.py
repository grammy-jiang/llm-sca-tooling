"""Workspace store — the top-level coordinator for local persistence.

Usage::

    store = await WorkspaceStore.initialize(Path("."))
    async with store:
        await store.registry.register_repo(Path("/my/repo"))
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from llm_sca_tooling.storage.artifacts import ArtifactStore
from llm_sca_tooling.storage.errors import (
    WorkspaceNotFoundError,
)
from llm_sca_tooling.storage.graph_queries import GraphQueryStore
from llm_sca_tooling.storage.graph_store import GraphStore
from llm_sca_tooling.storage.harness_store import HarnessMetadataStore
from llm_sca_tooling.storage.migrations import (
    CURRENT_VERSION,
    STORAGE_VERSION,
    MigrationManager,
)
from llm_sca_tooling.storage.operations import OperationalStore
from llm_sca_tooling.storage.paths import (
    artifacts_dir,
    exports_dir,
    locks_dir,
    sqlite_url,
)
from llm_sca_tooling.storage.registry import RepositoryRegistry
from llm_sca_tooling.storage.snapshots import SnapshotStore
from llm_sca_tooling.storage.sqlite import (
    AsyncSessionFactory,
    create_engine,
    create_session_factory,
    create_tables,
)
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["WorkspaceStore", "WorkspaceStatus"]

logger = get_logger(__name__)


@dataclass
class WorkspaceStatus:
    workspace_id: str
    storage_version: str
    applied_migrations: list[str]
    base_path: Path
    db_path: Path
    is_open: bool


class WorkspaceStore:
    """Top-level local persistence coordinator.

    Provides access to all sub-stores (registry, snapshots, graph, operations,
    harness metadata, artifacts) via a shared async session factory.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        session_factory: AsyncSessionFactory,
        base_path: Path,
        workspace_id: str,
    ) -> None:
        self._engine = engine
        self._session_factory = session_factory
        self._base_path = base_path
        self._workspace_id = workspace_id
        self._closed = False

        self.registry = RepositoryRegistry(session_factory)
        self.snapshots = SnapshotStore(session_factory)
        self.graph = GraphStore(session_factory)
        self.queries = GraphQueryStore(session_factory)
        self.operations = OperationalStore(session_factory)
        self.harness = HarnessMetadataStore(session_factory)
        self.artifacts = ArtifactStore(session_factory)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    async def initialize(
        cls, base_path: Path, *, in_memory: bool = False
    ) -> WorkspaceStore:
        """Create or open a workspace at *base_path*.

        - Creates `.llm-sca/` directory if it doesn't exist.
        - Creates all database tables (idempotent).
        - Applies any pending migrations.
        - Writes workspace metadata on first init.
        """
        if not in_memory:
            storage_root = base_path / ".llm-sca"
            storage_root.mkdir(parents=True, exist_ok=True)
            artifacts_dir(base_path).mkdir(parents=True, exist_ok=True)
            exports_dir(base_path).mkdir(parents=True, exist_ok=True)
            locks_dir(base_path).mkdir(parents=True, exist_ok=True)

        url = sqlite_url(base_path, in_memory=in_memory)
        engine = create_engine(url)
        await create_tables(engine)

        session_factory = create_session_factory(engine)
        workspace_id = str(uuid.uuid4())

        async with session_factory() as session, session.begin():
            manager = MigrationManager(session)
            await manager.apply_pending()
            workspace_id = await cls._ensure_metadata(session, workspace_id)

        logger.info(
            "Workspace initialized at %s", base_path if not in_memory else ":memory:"
        )
        return cls(engine, session_factory, base_path, workspace_id)

    @classmethod
    async def open(cls, base_path: Path) -> WorkspaceStore:
        """Open an existing workspace.  Fails if the database does not exist."""
        from llm_sca_tooling.storage.paths import db_path

        db = db_path(base_path)
        if not db.exists():
            raise WorkspaceNotFoundError(f"No workspace database at {db}")

        url = sqlite_url(base_path)
        engine = create_engine(url)
        await create_tables(engine)

        session_factory = create_session_factory(engine)

        async with session_factory() as session, session.begin():
            manager = MigrationManager(session)
            await manager.verify_checksums()
            workspace_id = await cls._read_metadata(session, "workspace_id") or str(
                uuid.uuid4()
            )

        logger.info("Workspace opened at %s", base_path)
        return cls(engine, session_factory, base_path, workspace_id)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def status(self) -> WorkspaceStatus:
        """Return workspace status including migration state."""
        from llm_sca_tooling.storage.paths import db_path

        async with self._session_factory() as session:
            manager = MigrationManager(session)
            applied = await manager.applied_versions()

        return WorkspaceStatus(
            workspace_id=self._workspace_id,
            storage_version=STORAGE_VERSION,
            applied_migrations=applied,
            base_path=self._base_path,
            db_path=db_path(self._base_path),
            is_open=not self._closed,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Dispose the engine and mark the workspace closed."""
        if not self._closed:
            await self._engine.dispose()
            self._closed = True

    async def __aenter__(self) -> WorkspaceStore:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _ensure_metadata(session: AsyncSession, workspace_id: str) -> str:
        now = datetime.now(UTC).isoformat()
        existing = await session.execute(
            text("SELECT value_json FROM workspace_metadata WHERE key = 'workspace_id'")
        )
        row = existing.fetchone()
        if row:
            return orjson.loads(row[0])

        rows = [
            ("workspace_id", orjson.dumps(workspace_id).decode()),
            ("storage_version", orjson.dumps(STORAGE_VERSION).decode()),
            ("created_ts", orjson.dumps(now).decode()),
            ("last_migration", orjson.dumps(CURRENT_VERSION).decode()),
        ]
        for key, value in rows:
            await session.execute(
                text(
                    "INSERT OR IGNORE INTO workspace_metadata (key, value_json, updated_ts) VALUES (:k, :v, :ts)"
                ),
                {"k": key, "v": value, "ts": now},
            )
        return workspace_id

    @staticmethod
    async def _read_metadata(session: AsyncSession, key: str) -> Any:
        result = await session.execute(
            text("SELECT value_json FROM workspace_metadata WHERE key = :k"),
            {"k": key},
        )
        row = result.fetchone()
        return orjson.loads(row[0]) if row else None
