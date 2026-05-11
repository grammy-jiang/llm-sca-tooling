"""Tests for storage transaction helpers."""

from __future__ import annotations

from sqlalchemy import text

from llm_sca_tooling.storage import WorkspaceStore
from llm_sca_tooling.storage.transactions import transaction


async def test_transaction_yields_session(workspace: WorkspaceStore) -> None:
    async with (
        workspace._session_factory() as session,
        transaction(session, "coverage") as tx,
    ):
        result = await tx.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
