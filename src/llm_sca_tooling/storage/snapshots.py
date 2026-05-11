"""Snapshot ledger — record and query repository snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import orjson
from sqlalchemy import select

from llm_sca_tooling.storage.errors import SnapshotNotFoundError
from llm_sca_tooling.storage.ids import generate_snapshot_id
from llm_sca_tooling.storage.models import SnapshotRow
from llm_sca_tooling.storage.sqlite import AsyncSessionFactory
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["SnapshotStore", "SnapshotRecord", "SnapshotMixResult"]

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class SnapshotRecord:
    snapshot_id: str
    repo_id: str
    git_sha: str | None
    branch: str | None
    dirty: bool
    worktree_snapshot_id: str | None
    index_status: str
    captured_ts: str
    source_run_id: str | None
    source_event_id: str | None
    file_state_hash: str | None


@dataclass
class SnapshotMixResult:
    """Summary of snapshot consistency for a set of snapshot IDs."""

    is_mixed: bool
    snapshot_ids: list[str]
    git_shas: list[str]
    dirty_count: int
    reason: str | None = None


def _row_to_record(row: SnapshotRow) -> SnapshotRecord:
    return SnapshotRecord(
        snapshot_id=row.snapshot_id,
        repo_id=row.repo_id,
        git_sha=row.git_sha,
        branch=row.branch,
        dirty=bool(row.dirty),
        worktree_snapshot_id=row.worktree_snapshot_id,
        index_status=row.index_status,
        captured_ts=row.captured_ts,
        source_run_id=row.source_run_id,
        source_event_id=row.source_event_id,
        file_state_hash=row.file_state_hash,
    )


class SnapshotStore:
    """CRUD and detection operations for repository snapshots."""

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    async def record_snapshot(
        self,
        repo_id: str,
        *,
        git_sha: str | None = None,
        branch: str | None = None,
        dirty: bool = False,
        worktree_snapshot_id: str | None = None,
        index_status: str = "unknown",
        source_run_id: str | None = None,
        source_event_id: str | None = None,
        file_state_hash: str | None = None,
    ) -> SnapshotRecord:
        """Record a new snapshot and return its record."""
        snapshot_id = generate_snapshot_id(repo_id, git_sha, worktree_snapshot_id)
        now = _now()

        async with self._session_factory() as session, session.begin():
            existing = await session.get(SnapshotRow, snapshot_id)
            if existing:
                return _row_to_record(existing)

            row = SnapshotRow(
                snapshot_id=snapshot_id,
                repo_id=repo_id,
                git_sha=git_sha,
                branch=branch,
                dirty=int(dirty),
                worktree_snapshot_id=worktree_snapshot_id,
                index_status=index_status,
                captured_ts=now,
                source_run_id=source_run_id,
                source_event_id=source_event_id,
                file_state_hash=file_state_hash,
                diagnostics_json="[]",
                metadata_json="{}",
            )
            session.add(row)
            logger.debug("Recorded snapshot %s for repo %s", snapshot_id, repo_id)
            return _row_to_record(row)

    async def get_snapshot(self, snapshot_id: str) -> SnapshotRecord:
        async with self._session_factory() as session:
            row = await session.get(SnapshotRow, snapshot_id)
        if row is None:
            raise SnapshotNotFoundError(f"Snapshot {snapshot_id!r} not found")
        return _row_to_record(row)

    async def get_latest_snapshot(
        self, repo_id: str, *, require_fresh: bool = False
    ) -> SnapshotRecord | None:
        async with self._session_factory() as session:
            stmt = (
                select(SnapshotRow)
                .where(SnapshotRow.repo_id == repo_id)
                .order_by(SnapshotRow.captured_ts.desc())
                .limit(1)
            )
            if require_fresh:
                stmt = stmt.where(SnapshotRow.index_status == "fresh")
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        return _row_to_record(row) if row else None

    async def list_snapshots(
        self,
        repo_id: str,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[SnapshotRecord]:
        async with self._session_factory() as session:
            stmt = (
                select(SnapshotRow)
                .where(SnapshotRow.repo_id == repo_id)
                .order_by(SnapshotRow.captured_ts.desc())
            )
            if status:
                stmt = stmt.where(SnapshotRow.index_status == status)
            if limit:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [_row_to_record(r) for r in rows]

    async def mark_snapshot_status(
        self, snapshot_id: str, status: str, diagnostics: list[dict] | None = None
    ) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(SnapshotRow, snapshot_id)
            if row is None:
                raise SnapshotNotFoundError(f"Snapshot {snapshot_id!r} not found")
            row.index_status = status
            if diagnostics is not None:
                row.diagnostics_json = orjson.dumps(diagnostics).decode()
            session.add(row)

    async def detect_mixed_snapshots(
        self, snapshot_ids: list[str]
    ) -> SnapshotMixResult:
        """Detect whether a set of snapshot IDs represents a mixed snapshot.

        A snapshot set is mixed when it contains more than one distinct git SHA,
        contains both clean and dirty snapshots, or includes any snapshot with
        index_status='mixed'.
        """
        if not snapshot_ids:
            return SnapshotMixResult(
                is_mixed=False, snapshot_ids=[], git_shas=[], dirty_count=0
            )

        async with self._session_factory() as session:
            result = await session.execute(
                select(SnapshotRow).where(SnapshotRow.snapshot_id.in_(snapshot_ids))
            )
            rows = result.scalars().all()

        git_shas = [r.git_sha for r in rows if r.git_sha]
        dirty_count = sum(1 for r in rows if r.dirty)
        unique_shas = set(git_shas)
        has_mixed_status = any(r.index_status == "mixed" for r in rows)

        is_mixed = False
        reason: str | None = None

        if len(unique_shas) > 1:
            is_mixed = True
            reason = f"multiple git SHAs: {sorted(unique_shas)}"
        elif dirty_count > 0 and len(rows) > dirty_count:
            is_mixed = True
            reason = f"mixed clean and dirty snapshots ({dirty_count} dirty)"
        elif has_mixed_status:
            is_mixed = True
            reason = "at least one snapshot has index_status=mixed"

        return SnapshotMixResult(
            is_mixed=is_mixed,
            snapshot_ids=snapshot_ids,
            git_shas=list(unique_shas),
            dirty_count=dirty_count,
            reason=reason,
        )
