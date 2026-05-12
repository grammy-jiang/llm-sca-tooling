"""Artifact registry — track large/external payloads by reference."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from llm_sca_tooling.storage.errors import ArtifactNotFoundError
from llm_sca_tooling.storage.models import ArtifactRow
from llm_sca_tooling.storage.sqlite import AsyncSessionFactory
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["ArtifactStore", "ArtifactHashResult"]

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ArtifactHashResult:
    def __init__(self, matched: bool, expected: str | None, actual: str | None) -> None:
        self.matched = matched
        self.expected = expected
        self.actual = actual


class ArtifactStore:
    """Record, retrieve, and verify artifact references."""

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    async def record_artifact(
        self,
        artifact_id: str,
        kind: str,
        uri: str,
        redaction_status: str,
        *,
        repo_id: str | None = None,
        run_id: str | None = None,
        sha256: str | None = None,
        size_bytes: int | None = None,
        media_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        async with self._session_factory() as session, session.begin():
            stmt = (
                sqlite_insert(ArtifactRow)
                .values(
                    artifact_id=artifact_id,
                    repo_id=repo_id,
                    run_id=run_id,
                    kind=kind,
                    uri=uri,
                    sha256=sha256,
                    size_bytes=size_bytes,
                    media_type=media_type,
                    redaction_status=redaction_status,
                    created_ts=_now(),
                    metadata_json=orjson.dumps(metadata or {}).decode(),
                )
                .on_conflict_do_nothing(index_elements=["artifact_id"])
            )
            await session.execute(stmt)
        return artifact_id

    async def get_artifact(self, artifact_id: str) -> dict[str, Any]:
        async with self._session_factory() as session:
            row = await session.get(ArtifactRow, artifact_id)
        if row is None:
            raise ArtifactNotFoundError(f"Artifact {artifact_id!r} not found")
        return {
            "artifact_id": row.artifact_id,
            "kind": row.kind,
            "uri": row.uri,
            "sha256": row.sha256,
            "size_bytes": row.size_bytes,
            "redaction_status": row.redaction_status,
        }

    async def list_artifacts(
        self,
        repo_id: str | None = None,
        run_id: str | None = None,
        kind: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = select(ArtifactRow).limit(limit)
            if repo_id:
                stmt = stmt.where(ArtifactRow.repo_id == repo_id)
            if run_id:
                stmt = stmt.where(ArtifactRow.run_id == run_id)
            if kind:
                stmt = stmt.where(ArtifactRow.kind == kind)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [
            {
                "artifact_id": r.artifact_id,
                "kind": r.kind,
                "uri": r.uri,
                "sha256": r.sha256,
                "redaction_status": r.redaction_status,
            }
            for r in rows
        ]

    async def verify_artifact_hash(self, artifact_id: str) -> ArtifactHashResult:
        """Verify the SHA-256 hash of an artifact's file content."""
        async with self._session_factory() as session:
            row = await session.get(ArtifactRow, artifact_id)
        if row is None:
            raise ArtifactNotFoundError(f"Artifact {artifact_id!r} not found")

        if not row.sha256:
            return ArtifactHashResult(matched=True, expected=None, actual=None)

        # Resolve local path
        uri = row.uri
        if uri.startswith("file://"):
            path = Path(uri[7:])
        else:
            path = Path(uri)

        if not path.exists():
            logger.warning("Artifact file not found: %s", path)
            return ArtifactHashResult(matched=False, expected=row.sha256, actual=None)

        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        return ArtifactHashResult(
            matched=(actual == row.sha256), expected=row.sha256, actual=actual
        )
