"""SQLite-backed embedding vector cache."""

from __future__ import annotations

import hashlib
from sqlite3 import Connection

import orjson
from pydantic import Field

from llm_sca_tooling.fl.embedding_interface import EmbeddingVector
from llm_sca_tooling.schemas.base import StrictBaseModel, parse_utc_ts
from llm_sca_tooling.storage.workspace import _now_ts


class VectorCacheStats(StrictBaseModel):
    total_entries: int = Field(ge=0)
    valid_entries: int = Field(ge=0)
    stale_entries: int = Field(ge=0)
    hit_rate: float = Field(ge=0.0, le=1.0)
    last_purge_ts: str | None = None


class VectorCache:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn
        self._ensure_table()

    def store(
        self,
        node_id: str,
        model_id: str,
        git_sha: str,
        vector: EmbeddingVector,
        *,
        worktree_snapshot_id: str | None = None,
        expires_ts: str | None = None,
    ) -> None:
        cache_key = self.cache_key(node_id, model_id, git_sha, worktree_snapshot_id)
        node_row = self.conn.execute(
            "SELECT repo_id, file_path FROM graph_nodes WHERE node_id=?", (node_id,)
        ).fetchone()
        repo_id = str(node_row["repo_id"]) if node_row else None
        file_path = (
            str(node_row["file_path"]) if node_row and node_row["file_path"] else None
        )
        self.conn.execute(
            """
            INSERT INTO embedding_vectors(
              cache_key, repo_id, file_path, node_id, model_id, git_sha,
              worktree_snapshot_id, vector_blob, dimensions, text_hash,
              produced_ts, expires_ts, hit_count, last_hit_ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
            ON CONFLICT(cache_key) DO UPDATE SET
              vector_blob=excluded.vector_blob,
              dimensions=excluded.dimensions,
              text_hash=excluded.text_hash,
              produced_ts=excluded.produced_ts,
              expires_ts=excluded.expires_ts
            """,
            (
                cache_key,
                repo_id,
                file_path,
                node_id,
                model_id,
                git_sha,
                worktree_snapshot_id,
                orjson.dumps(vector.model_dump(mode="json")),
                vector.dimensions,
                vector.text_hash,
                vector.produced_ts,
                expires_ts,
            ),
        )
        self.conn.commit()

    def get(
        self,
        node_id: str,
        model_id: str,
        git_sha: str,
        *,
        worktree_snapshot_id: str | None = None,
    ) -> EmbeddingVector | None:
        cache_key = self.cache_key(node_id, model_id, git_sha, worktree_snapshot_id)
        row = self.conn.execute(
            "SELECT vector_blob, expires_ts FROM embedding_vectors WHERE cache_key=?",
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        if row["expires_ts"] and parse_utc_ts(str(row["expires_ts"])) <= parse_utc_ts(
            _now_ts()
        ):
            return None
        self.conn.execute(
            "UPDATE embedding_vectors SET hit_count=hit_count+1, last_hit_ts=? WHERE cache_key=?",
            (_now_ts(), cache_key),
        )
        self.conn.commit()
        return EmbeddingVector.model_validate(orjson.loads(row["vector_blob"]))

    def invalidate_file(self, file_path: str, repo_id: str, new_git_sha: str) -> int:
        _ = new_git_sha
        row = self.conn.execute(
            "SELECT count(*) AS count FROM embedding_vectors WHERE repo_id=? AND file_path=?",
            (repo_id, file_path),
        ).fetchone()
        self.conn.execute(
            "DELETE FROM embedding_vectors WHERE repo_id=? AND file_path=?",
            (repo_id, file_path),
        )
        self.conn.commit()
        return int(row["count"]) if row else 0

    def invalidate_repo(self, repo_id: str, new_git_sha: str) -> int:
        row = self.conn.execute(
            "SELECT count(*) AS count FROM embedding_vectors WHERE repo_id=? AND git_sha<>?",
            (repo_id, new_git_sha),
        ).fetchone()
        self.conn.execute(
            "DELETE FROM embedding_vectors WHERE repo_id=? AND git_sha<>?",
            (repo_id, new_git_sha),
        )
        self.conn.commit()
        return int(row["count"]) if row else 0

    def purge_expired(self) -> int:
        now = _now_ts()
        row = self.conn.execute(
            "SELECT count(*) AS count FROM embedding_vectors WHERE expires_ts IS NOT NULL AND expires_ts<=?",
            (now,),
        ).fetchone()
        self.conn.execute(
            "DELETE FROM embedding_vectors WHERE expires_ts IS NOT NULL AND expires_ts<=?",
            (now,),
        )
        self.conn.execute(
            """
            INSERT INTO workspace_metadata(key, value_json, updated_ts)
            VALUES ('embedding_vector_cache_last_purge_ts', json_quote(?), ?)
            ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_ts=excluded.updated_ts
            """,
            (now, now),
        )
        self.conn.commit()
        return int(row["count"]) if row else 0

    def stats(self) -> VectorCacheStats:
        now = _now_ts()
        total = int(
            self.conn.execute(
                "SELECT count(*) AS count FROM embedding_vectors"
            ).fetchone()["count"]
        )
        valid = int(
            self.conn.execute(
                "SELECT count(*) AS count FROM embedding_vectors WHERE expires_ts IS NULL OR expires_ts>?",
                (now,),
            ).fetchone()["count"]
        )
        hits = int(
            self.conn.execute(
                "SELECT coalesce(sum(hit_count), 0) AS count FROM embedding_vectors"
            ).fetchone()["count"]
        )
        metadata = self.conn.execute(
            "SELECT value_json FROM workspace_metadata WHERE key='embedding_vector_cache_last_purge_ts'"
        ).fetchone()
        last_purge = None
        if metadata is not None:
            last_purge = str(orjson.loads(metadata["value_json"]))
        return VectorCacheStats(
            total_entries=total,
            valid_entries=valid,
            stale_entries=max(0, total - valid),
            hit_rate=0.0 if hits == 0 else min(1.0, hits / max(hits + total, 1)),
            last_purge_ts=last_purge,
        )

    @staticmethod
    def cache_key(
        node_id: str,
        model_id: str,
        git_sha: str,
        worktree_snapshot_id: str | None = None,
    ) -> str:
        payload = "|".join([node_id, model_id, git_sha, worktree_snapshot_id or ""])
        return "embedding:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _ensure_table(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS embedding_vectors (
              cache_key TEXT PRIMARY KEY,
              repo_id TEXT,
              file_path TEXT,
              node_id TEXT NOT NULL,
              model_id TEXT NOT NULL,
              git_sha TEXT NOT NULL,
              worktree_snapshot_id TEXT,
              vector_blob BLOB NOT NULL,
              dimensions INTEGER NOT NULL,
              text_hash TEXT NOT NULL,
              produced_ts TEXT NOT NULL,
              expires_ts TEXT,
              hit_count INTEGER NOT NULL DEFAULT 0,
              last_hit_ts TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_embedding_node ON embedding_vectors(node_id, model_id);
            CREATE INDEX IF NOT EXISTS idx_embedding_git_sha ON embedding_vectors(git_sha);
            CREATE INDEX IF NOT EXISTS idx_embedding_repo_file ON embedding_vectors(repo_id, file_path);
            """)
        self.conn.commit()
