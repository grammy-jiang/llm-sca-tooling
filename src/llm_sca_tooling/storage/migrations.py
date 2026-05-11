"""Migration manager for the local workspace store.

Phase 2 uses a hand-rolled migration tracker.  The initial migration (0001)
creates all tables via SQLModel.  Future migrations will use Alembic
``op.batch_alter_table`` for SQLite compatibility.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from llm_sca_tooling.storage.errors import MigrationError
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["MigrationManager", "CURRENT_VERSION"]

logger = get_logger(__name__)

CURRENT_VERSION = "0001"
STORAGE_VERSION = "0.1.0"


@dataclass
class MigrationRecord:
    version: str
    applied_ts: str
    checksum: str
    description: str


def _checksum(version: str, description: str) -> str:
    return hashlib.sha256(f"{version}:{description}".encode()).hexdigest()[:16]


_MIGRATIONS: list[MigrationRecord] = [
    MigrationRecord(
        version="0001",
        applied_ts="",
        checksum=_checksum("0001", "Initial schema"),
        description="Initial schema",
    )
]


class MigrationManager:
    """Tracks and applies database schema migrations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def applied_versions(self) -> list[str]:
        """Return all applied migration versions from the database."""
        try:
            result = await self._session.execute(
                text("SELECT version FROM schema_migrations ORDER BY version")
            )
            return [row[0] for row in result.fetchall()]
        except Exception:
            return []

    async def record_migration(self, record: MigrationRecord) -> None:
        """Write a migration record to the database."""
        ts = datetime.now(UTC).isoformat()
        await self._session.execute(
            text(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_ts, checksum, description) "
                "VALUES (:v, :ts, :cs, :desc)"
            ),
            {
                "v": record.version,
                "ts": ts,
                "cs": record.checksum,
                "desc": record.description,
            },
        )

    async def verify_checksums(self) -> None:
        """Raise MigrationError if any stored checksum does not match."""
        try:
            result = await self._session.execute(
                text("SELECT version, checksum FROM schema_migrations")
            )
            stored = {row[0]: row[1] for row in result.fetchall()}
        except Exception:
            return

        expected = {m.version: m.checksum for m in _MIGRATIONS}
        for version, checksum in stored.items():
            if version in expected and expected[version] != checksum:
                raise MigrationError(
                    f"Migration {version!r} checksum mismatch: "
                    f"expected {expected[version]!r}, got {checksum!r}"
                )

    async def apply_pending(self) -> list[str]:
        """Apply any migrations that have not yet been recorded.

        Returns the list of newly applied migration versions.
        """
        applied = set(await self.applied_versions())
        newly_applied: list[str] = []

        for migration in _MIGRATIONS:
            if migration.version not in applied:
                logger.info(
                    "Applying migration %s: %s",
                    migration.version,
                    migration.description,
                )
                await self.record_migration(migration)
                newly_applied.append(migration.version)

        # if newly_applied: (commit handled by caller)

        return newly_applied
