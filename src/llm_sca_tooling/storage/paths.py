"""Storage path utilities."""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "DEFAULT_STORAGE_DIR",
    "DEFAULT_DB_NAME",
    "storage_dir",
    "db_path",
    "artifacts_dir",
    "exports_dir",
    "locks_dir",
    "sqlite_url",
]

DEFAULT_STORAGE_DIR = ".llm-sca"
DEFAULT_DB_NAME = "workspace.db"


def storage_dir(base: Path) -> Path:
    """Return the storage root for *base* (the repo root or workspace path)."""
    return base / DEFAULT_STORAGE_DIR


def db_path(base: Path) -> Path:
    """Return the SQLite database path."""
    return storage_dir(base) / DEFAULT_DB_NAME


def artifacts_dir(base: Path) -> Path:
    return storage_dir(base) / "artifacts"


def exports_dir(base: Path) -> Path:
    return storage_dir(base) / "exports"


def locks_dir(base: Path) -> Path:
    return storage_dir(base) / "locks"


def sqlite_url(base: Path | str, *, in_memory: bool = False) -> str:
    """Return the aiosqlite connection URL."""
    if in_memory:
        return "sqlite+aiosqlite:///:memory:"
    path = db_path(Path(base)) if isinstance(base, str) else db_path(base)
    return f"sqlite+aiosqlite:///{path}"
