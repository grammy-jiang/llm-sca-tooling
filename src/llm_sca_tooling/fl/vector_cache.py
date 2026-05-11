"""SQLite-backed embedding vector cache."""

from __future__ import annotations

from datetime import UTC, datetime

import orjson
from sqlalchemy import text

from llm_sca_tooling.fl.embedding_interface import EmbeddingVector
from llm_sca_tooling.fl.models import StrictFlModel
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["VectorCache", "VectorCacheStats"]


class VectorCacheStats(StrictFlModel):
    total_entries: int
    valid_entries: int
    stale_entries: int
    hit_rate: float = 0.0
    last_purge_ts: str | None = None


class VectorCache:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self._workspace = workspace
        self._hits = 0
        self._misses = 0
        self._last_purge_ts: str | None = None

    async def _ensure_schema(self) -> None:
        async with self._workspace._session_factory() as session:
            await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS embedding_vectors (
                        cache_key TEXT PRIMARY KEY,
                        node_id TEXT NOT NULL,
                        repo_id TEXT NOT NULL,
                        file_path TEXT,
                        model_id TEXT NOT NULL,
                        git_sha TEXT NOT NULL,
                        worktree_snapshot_id TEXT,
                        vector_blob BLOB NOT NULL,
                        dimensions INTEGER NOT NULL,
                        text_hash TEXT NOT NULL,
                        produced_ts TEXT NOT NULL,
                        expires_ts TEXT
                    )
                    """))
            await session.commit()

    async def store(
        self,
        node_id: str,
        model_id: str,
        git_sha: str,
        vector: EmbeddingVector,
        *,
        repo_id: str,
        file_path: str | None = None,
        worktree_snapshot_id: str | None = None,
        expires_ts: str | None = None,
    ) -> None:
        await self._ensure_schema()
        async with self._workspace._session_factory() as session:
            await session.execute(
                text("""
                    INSERT OR REPLACE INTO embedding_vectors
                    (cache_key, node_id, repo_id, file_path, model_id, git_sha,
                     worktree_snapshot_id, vector_blob, dimensions, text_hash,
                     produced_ts, expires_ts)
                    VALUES
                    (:cache_key, :node_id, :repo_id, :file_path, :model_id, :git_sha,
                     :worktree_snapshot_id, :vector_blob, :dimensions, :text_hash,
                     :produced_ts, :expires_ts)
                    """),
                {
                    "cache_key": self._key(node_id, model_id, git_sha),
                    "node_id": node_id,
                    "repo_id": repo_id,
                    "file_path": file_path,
                    "model_id": model_id,
                    "git_sha": git_sha,
                    "worktree_snapshot_id": worktree_snapshot_id,
                    "vector_blob": orjson.dumps(vector.model_dump(mode="json")),
                    "dimensions": vector.dimensions,
                    "text_hash": vector.text_hash,
                    "produced_ts": vector.produced_ts,
                    "expires_ts": expires_ts,
                },
            )
            await session.commit()

    async def get(
        self, node_id: str, model_id: str, git_sha: str
    ) -> EmbeddingVector | None:
        await self._ensure_schema()
        async with self._workspace._session_factory() as session:
            row = (
                await session.execute(
                    text("""
                        SELECT vector_blob FROM embedding_vectors
                        WHERE cache_key = :cache_key
                        AND (expires_ts IS NULL OR expires_ts > :now)
                        """),
                    {
                        "cache_key": self._key(node_id, model_id, git_sha),
                        "now": datetime.now(UTC).isoformat(),
                    },
                )
            ).first()
        if row is None:
            self._misses += 1
            return None
        self._hits += 1
        return EmbeddingVector.model_validate(orjson.loads(row[0]))

    async def invalidate_file(
        self, file_path: str, repo_id: str, new_git_sha: str
    ) -> int:
        del new_git_sha
        await self._ensure_schema()
        async with self._workspace._session_factory() as session:
            result = await session.execute(
                text(
                    "DELETE FROM embedding_vectors "
                    "WHERE repo_id = :repo_id AND file_path = :file_path"
                ),
                {"repo_id": repo_id, "file_path": file_path},
            )
            await session.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    async def invalidate_repo(self, repo_id: str, new_git_sha: str) -> int:
        await self._ensure_schema()
        async with self._workspace._session_factory() as session:
            result = await session.execute(
                text(
                    "DELETE FROM embedding_vectors "
                    "WHERE repo_id = :repo_id AND git_sha != :git_sha"
                ),
                {"repo_id": repo_id, "git_sha": new_git_sha},
            )
            await session.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    async def purge_expired(self) -> int:
        await self._ensure_schema()
        now = datetime.now(UTC).isoformat()
        async with self._workspace._session_factory() as session:
            result = await session.execute(
                text(
                    "DELETE FROM embedding_vectors "
                    "WHERE expires_ts IS NOT NULL AND expires_ts <= :now"
                ),
                {"now": now},
            )
            await session.commit()
        self._last_purge_ts = now
        return int(getattr(result, "rowcount", 0) or 0)

    async def stats(self) -> VectorCacheStats:
        await self._ensure_schema()
        async with self._workspace._session_factory() as session:
            total = (
                await session.execute(text("SELECT COUNT(*) FROM embedding_vectors"))
            ).scalar_one()
            valid = (
                await session.execute(
                    text(
                        "SELECT COUNT(*) FROM embedding_vectors "
                        "WHERE expires_ts IS NULL OR expires_ts > :now"
                    ),
                    {"now": datetime.now(UTC).isoformat()},
                )
            ).scalar_one()
        requests = self._hits + self._misses
        return VectorCacheStats(
            total_entries=int(total),
            valid_entries=int(valid),
            stale_entries=int(total) - int(valid),
            hit_rate=(self._hits / requests) if requests else 0.0,
            last_purge_ts=self._last_purge_ts,
        )

    @staticmethod
    def _key(node_id: str, model_id: str, git_sha: str) -> str:
        return f"{node_id}:{model_id}:{git_sha}"
