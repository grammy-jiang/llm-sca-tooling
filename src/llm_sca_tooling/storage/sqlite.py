"""Async SQLite connection manager.

All database access goes through :class:`AsyncEngine` / :class:`AsyncSession`.
SQLite-specific PRAGMAs (WAL, foreign keys, busy timeout) are applied on
every connection via a ``@event.listens_for`` hook.

For in-memory databases (testing) we use ``StaticPool`` to ensure all
async sessions share the same underlying connection.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["create_engine", "create_session_factory", "AsyncSessionFactory"]

logger = get_logger(__name__)

AsyncSessionFactory = async_sessionmaker[AsyncSession]

_PRAGMAS = [
    "PRAGMA foreign_keys = ON",
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA busy_timeout = 5000",
]

_IN_MEMORY_URL = "sqlite+aiosqlite:///:memory:"


def create_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    """Create an async engine with SQLite-specific PRAGMAs applied on connect.

    In-memory databases use :class:`StaticPool` so all sessions share one
    connection.  File-based databases use the default pool.
    """
    is_memory = url == _IN_MEMORY_URL

    kwargs: dict = {"echo": echo, "future": True}
    if is_memory:
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_async_engine(url, **kwargs)

    @sa.event.listens_for(engine.sync_engine, "connect")
    def _set_pragmas(dbapi_conn: object, _conn_record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[union-attr]
        for pragma in _PRAGMAS:
            cursor.execute(pragma)
        cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> AsyncSessionFactory:
    """Return an async session factory for *engine*."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_tables(engine: AsyncEngine) -> None:
    """Create all SQLModel tables against *engine* (idempotent)."""
    import llm_sca_tooling.storage.models  # noqa: F401 — registers table metadata

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.debug("Tables created via SQLModel.metadata.create_all")
