"""Lazy SQLite store for interface records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import orjson
from sqlalchemy import text

from llm_sca_tooling.plugins.interface_record import InterfaceRecord
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["InterfaceRecordStore"]


class InterfaceRecordStore:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self._workspace = workspace

    async def _ensure_schema(self) -> None:
        async with self._workspace._session_factory() as session:
            await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS interface_records (
                        interface_id TEXT PRIMARY KEY,
                        plugin_id TEXT NOT NULL,
                        interface_name TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        repo_ids_json TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        superseded INTEGER NOT NULL DEFAULT 0,
                        last_indexed_ts TEXT NOT NULL
                    )
                    """))
            await session.commit()

    async def store_records(self, records: list[InterfaceRecord]) -> None:
        await self._ensure_schema()
        now = datetime.now(UTC).isoformat()
        async with self._workspace._session_factory() as session:
            for record in records:
                await session.execute(
                    text("""
                        INSERT OR REPLACE INTO interface_records
                        (interface_id, plugin_id, interface_name, kind, repo_ids_json,
                         record_json, superseded, last_indexed_ts)
                        VALUES
                        (:interface_id, :plugin_id, :interface_name, :kind,
                         :repo_ids_json, :record_json, 0, :last_indexed_ts)
                        """),
                    {
                        "interface_id": record.interface_id,
                        "plugin_id": record.plugin_id,
                        "interface_name": record.interface_name,
                        "kind": record.kind.value,
                        "repo_ids_json": orjson.dumps(record.source_repos).decode(),
                        "record_json": record.model_dump_json(by_alias=True),
                        "last_indexed_ts": now,
                    },
                )
            await session.commit()

    async def list_records(self, plugin_id: str | None = None) -> list[InterfaceRecord]:
        await self._ensure_schema()
        query = "SELECT record_json FROM interface_records WHERE superseded = 0"
        params: dict[str, Any] = {}
        if plugin_id:
            query += " AND plugin_id = :plugin_id"
            params["plugin_id"] = plugin_id
        query += " ORDER BY plugin_id, interface_name"
        async with self._workspace._session_factory() as session:
            rows = (await session.execute(text(query), params)).all()
        return [InterfaceRecord.model_validate_json(str(row[0])) for row in rows]

    async def get_record(
        self, plugin_id: str, interface_name: str
    ) -> InterfaceRecord | None:
        await self._ensure_schema()
        async with self._workspace._session_factory() as session:
            row = (
                await session.execute(
                    text("""
                        SELECT record_json FROM interface_records
                        WHERE plugin_id = :plugin_id
                        AND interface_name = :interface_name
                        AND superseded = 0
                        """),
                    {"plugin_id": plugin_id, "interface_name": interface_name},
                )
            ).first()
        return InterfaceRecord.model_validate_json(str(row[0])) if row else None
