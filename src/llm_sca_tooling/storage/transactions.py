"""Transaction context helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["transaction"]


@asynccontextmanager
async def transaction(
    session: AsyncSession, reason: str = ""
) -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that wraps *session* in a savepoint transaction.

    Usage::

        async with transaction(session, "batch graph write"):
            session.add(row)
    """
    async with session.begin_nested():
        yield session
