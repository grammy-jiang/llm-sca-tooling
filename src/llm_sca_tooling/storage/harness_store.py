"""Harness metadata store — manifests, permission profiles, supply-chain records."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import orjson
from sqlalchemy import select

from llm_sca_tooling.storage.ids import new_uuid
from llm_sca_tooling.storage.models import HarnessMetadataRow, SupplyChainRow
from llm_sca_tooling.storage.sqlite import AsyncSessionFactory
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["HarnessMetadataStore"]

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    ).hexdigest()[:24]


class HarnessMetadataStore:
    """Store and retrieve harness control-plane metadata."""

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    async def put_harness_metadata(
        self,
        repo_id: str | None,
        kind: str,
        payload: dict[str, Any],
        *,
        active: bool = True,
    ) -> str:
        metadata_id = new_uuid("hm")
        now = _now()
        async with self._session_factory() as session, session.begin():
            row = HarnessMetadataRow(
                metadata_id=metadata_id,
                repo_id=repo_id,
                kind=kind,
                active=int(active),
                payload_json=orjson.dumps(payload).decode(),
                payload_hash=_payload_hash(payload),
                created_ts=now,
                updated_ts=now,
            )
            session.add(row)
        return metadata_id

    async def get_harness_metadata(
        self,
        repo_id: str | None,
        kind: str,
        *,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = select(HarnessMetadataRow).where(HarnessMetadataRow.kind == kind)
            if repo_id is not None:
                stmt = stmt.where(HarnessMetadataRow.repo_id == repo_id)
            if active_only:
                stmt = stmt.where(HarnessMetadataRow.active == 1)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [
            {
                "metadata_id": r.metadata_id,
                "kind": r.kind,
                **orjson.loads(r.payload_json),
            }
            for r in rows
        ]

    async def record_supply_chain_record(
        self,
        component_type: str,
        name: str,
        version: str,
        payload: dict[str, Any],
        *,
        repo_id: str | None = None,
        source: str | None = None,
        hash_value: str | None = None,
    ) -> str:
        record_id = new_uuid("sc")
        async with self._session_factory() as session, session.begin():
            row = SupplyChainRow(
                supply_chain_record_id=record_id,
                repo_id=repo_id,
                component_type=component_type,
                name=name,
                version=version,
                source=source,
                hash=hash_value,
                payload_json=orjson.dumps(payload).decode(),
                captured_ts=_now(),
            )
            session.add(row)
        return record_id

    async def list_supply_chain_records(
        self,
        repo_id: str | None = None,
        component_type: str | None = None,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = select(SupplyChainRow)
            if repo_id is not None:
                stmt = stmt.where(SupplyChainRow.repo_id == repo_id)
            if component_type is not None:
                stmt = stmt.where(SupplyChainRow.component_type == component_type)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [
            {
                "supply_chain_record_id": r.supply_chain_record_id,
                "component_type": r.component_type,
                "name": r.name,
                "version": r.version,
            }
            for r in rows
        ]
