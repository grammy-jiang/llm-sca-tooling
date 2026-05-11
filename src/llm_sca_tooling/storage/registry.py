"""Repository registry — register, list, and query repositories."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson
from sqlalchemy import select

from llm_sca_tooling.storage.errors import (
    RepositoryNotFoundError,
)
from llm_sca_tooling.storage.ids import generate_repo_id, hash_path, hash_url
from llm_sca_tooling.storage.models import RepositoryRow
from llm_sca_tooling.storage.sqlite import AsyncSessionFactory
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["RepositoryRegistry", "RepositoryRecord"]

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _detect_git_branch(path: Path) -> str | None:
    try:
        result = subprocess.run(  # noqa: S603,S607
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def _row_to_record(row: RepositoryRow) -> RepositoryRecord:
    capabilities: dict[str, Any] = orjson.loads(row.capabilities_json)
    metadata: dict[str, Any] = orjson.loads(row.metadata_json)
    return RepositoryRecord(
        repo_id=row.repo_id,
        name=row.name,
        root_path=Path(row.root_path),
        root_path_hash=row.root_path_hash,
        vcs_type=row.vcs_type,
        remote_url_hash=row.remote_url_hash,
        default_branch=row.default_branch,
        current_branch=row.current_branch,
        registered_ts=row.registered_ts,
        last_seen_ts=row.last_seen_ts,
        active=bool(row.active),
        index_status=row.index_status,
        latest_snapshot_id=row.latest_snapshot_id,
        capabilities=capabilities,
        metadata=metadata,
    )


class RepositoryRecord:
    def __init__(
        self,
        repo_id: str,
        name: str,
        root_path: Path,
        root_path_hash: str,
        vcs_type: str,
        remote_url_hash: str | None,
        default_branch: str | None,
        current_branch: str | None,
        registered_ts: str,
        last_seen_ts: str,
        active: bool,
        index_status: str,
        latest_snapshot_id: str | None,
        capabilities: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        self.repo_id = repo_id
        self.name = name
        self.root_path = root_path
        self.root_path_hash = root_path_hash
        self.vcs_type = vcs_type
        self.remote_url_hash = remote_url_hash
        self.default_branch = default_branch
        self.current_branch = current_branch
        self.registered_ts = registered_ts
        self.last_seen_ts = last_seen_ts
        self.active = active
        self.index_status = index_status
        self.latest_snapshot_id = latest_snapshot_id
        self.capabilities = capabilities
        self.metadata = metadata

    def redacted(self) -> dict[str, Any]:
        """Return public metadata without absolute paths or sensitive data."""
        return {
            "repo_id": self.repo_id,
            "name": self.name,
            "root_path_hash": self.root_path_hash,
            "vcs_type": self.vcs_type,
            "remote_url_hash": self.remote_url_hash,
            "default_branch": self.default_branch,
            "index_status": self.index_status,
            "active": self.active,
        }


class RepositoryRegistry:
    """CRUD operations for registered repositories."""

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    async def register_repo(
        self,
        path: Path,
        *,
        name: str | None = None,
        remote_url: str | None = None,
        vcs_type: str = "git",
    ) -> RepositoryRecord:
        """Register a repository.  Idempotent — re-registering the same path updates last_seen_ts."""
        canonical = path.resolve()
        if not canonical.exists():
            raise ValueError(f"Repository path does not exist: {canonical}")

        repo_id = generate_repo_id(canonical, remote_url)
        repo_name = name or canonical.name
        now = _now()

        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                select(RepositoryRow).where(RepositoryRow.repo_id == repo_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.last_seen_ts = now
                existing.active = 1
                session.add(existing)
                return _row_to_record(existing)

            branch = _detect_git_branch(canonical)
            row = RepositoryRow(
                repo_id=repo_id,
                name=repo_name,
                root_path=str(canonical),
                root_path_hash=hash_path(canonical),
                vcs_type=vcs_type,
                remote_url_hash=hash_url(remote_url) if remote_url else None,
                current_branch=branch,
                registered_ts=now,
                last_seen_ts=now,
                active=1,
                index_status="not_indexed",
                capabilities_json="{}",
                metadata_json="{}",
            )
            session.add(row)
            logger.info("Registered repository %s at %s", repo_id, canonical)
            return _row_to_record(row)

    async def get_repo(self, repo_id: str) -> RepositoryRecord:
        async with self._session_factory() as session:
            result = await session.execute(
                select(RepositoryRow).where(RepositoryRow.repo_id == repo_id)
            )
            row = result.scalar_one_or_none()
        if row is None:
            raise RepositoryNotFoundError(f"Repository {repo_id!r} not found")
        return _row_to_record(row)

    async def list_repos(self, *, active_only: bool = True) -> list[RepositoryRecord]:
        async with self._session_factory() as session:
            stmt = select(RepositoryRow)
            if active_only:
                stmt = stmt.where(RepositoryRow.active == 1)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [_row_to_record(r) for r in rows]

    async def set_latest_snapshot(self, repo_id: str, snapshot_id: str) -> None:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                select(RepositoryRow).where(RepositoryRow.repo_id == repo_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise RepositoryNotFoundError(f"Repository {repo_id!r} not found")
            row.latest_snapshot_id = snapshot_id
            row.last_seen_ts = _now()
            session.add(row)

    async def update_status(self, repo_id: str, index_status: str) -> None:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                select(RepositoryRow).where(RepositoryRow.repo_id == repo_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise RepositoryNotFoundError(f"Repository {repo_id!r} not found")
            row.index_status = index_status
            row.last_seen_ts = _now()
            session.add(row)

    async def unregister_repo(
        self, repo_id: str, *, keep_evidence: bool = True
    ) -> RepositoryRecord:
        """Unregister a repository.  With keep_evidence=True, marks inactive but preserves rows."""
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                select(RepositoryRow).where(RepositoryRow.repo_id == repo_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise RepositoryNotFoundError(f"Repository {repo_id!r} not found")
            record = _row_to_record(row)
            if keep_evidence:
                row.active = 0
                session.add(row)
            else:
                await session.delete(row)
            return record
