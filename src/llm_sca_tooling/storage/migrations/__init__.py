"""SQLite migration runner and bundled migrations."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from importlib import resources

from llm_sca_tooling.storage.errors import MigrationError, WorkspaceIncompatibleError

STORAGE_VERSION = "0.1.0"


@dataclass(frozen=True)
class Migration:
    version: str
    description: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


def available_migrations() -> list[Migration]:
    sql = resources.files(__package__).joinpath("0001_initial.sql").read_text(encoding="utf-8")
    return [Migration("0001", "initial local graph store", sql)]


def apply_migrations(conn: sqlite3.Connection) -> None:
    migrations = {migration.version: migration for migration in available_migrations()}
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version TEXT PRIMARY KEY,
          applied_ts TEXT NOT NULL,
          checksum TEXT NOT NULL,
          description TEXT NOT NULL
        )
        """
    )
    rows = conn.execute("SELECT version, checksum FROM schema_migrations ORDER BY version").fetchall()
    for row in rows:
        if row["version"] not in migrations:
            raise WorkspaceIncompatibleError(f"unknown future migration {row['version']}")
        if row["checksum"] != migrations[row["version"]].checksum:
            raise MigrationError(f"migration checksum mismatch for {row['version']}")
    applied = {row["version"] for row in rows}
    for migration in sorted(migrations.values(), key=lambda item: item.version):
        if migration.version in applied:
            continue
        conn.executescript(migration.sql)
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_ts, checksum, description) VALUES (?, datetime('now'), ?, ?)",
            (migration.version, migration.checksum, migration.description),
        )
    conn.commit()
