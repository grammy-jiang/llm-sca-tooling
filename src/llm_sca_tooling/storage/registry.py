"""Repository registry store."""

from __future__ import annotations

import json
from pathlib import Path
from sqlite3 import Connection

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel
from llm_sca_tooling.storage.errors import DuplicateRepositoryError, RepositoryNotFoundError
from llm_sca_tooling.storage.ids import repo_id_for
from llm_sca_tooling.storage.paths import detect_current_branch, detect_default_branch, detect_remote_url_hash, detect_vcs_type, normalize_root, path_hash
from llm_sca_tooling.storage.workspace import _now_ts


class RegisteredRepository(StrictBaseModel):
    repo_id: str
    name: str
    root_path: str
    root_path_hash: str
    vcs_type: str
    remote_url_hash: str | None = None
    default_branch: str | None = None
    current_branch: str | None = None
    registered_ts: str
    last_seen_ts: str
    active: bool
    index_status: str
    latest_snapshot_id: str | None = None
    capabilities: JsonObject = Field(default_factory=dict)
    metadata: JsonObject = Field(default_factory=dict)

    def public_metadata(self) -> JsonObject:
        return {
            "repo_id": self.repo_id,
            "name": self.name,
            "root_path_hash": self.root_path_hash,
            "vcs_type": self.vcs_type,
            "remote_url_hash": self.remote_url_hash,
            "default_branch": self.default_branch,
            "current_branch": self.current_branch,
            "active": self.active,
            "index_status": self.index_status,
            "latest_snapshot_id": self.latest_snapshot_id,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
        }


class RepositoryRegistry:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def register_repo(self, path: str | Path, *, name: str | None = None, policy_scope: JsonObject | None = None) -> RegisteredRepository:
        root = normalize_root(path)
        if not root.exists():
            raise RepositoryNotFoundError(f"repository root does not exist: {root}")
        row = self.conn.execute("SELECT * FROM repositories WHERE root_path = ?", (str(root),)).fetchone()
        now = _now_ts()
        display_name = name or root.name
        if row:
            self.conn.execute("UPDATE repositories SET last_seen_ts=?, active=1 WHERE repo_id=?", (now, row["repo_id"]))
            self.conn.commit()
            return self._from_row(self.conn.execute("SELECT * FROM repositories WHERE repo_id=?", (row["repo_id"],)).fetchone())
        repo_id = repo_id_for(str(root), name=display_name)
        metadata: JsonObject = {}
        if policy_scope is not None:
            metadata["policy_scope"] = policy_scope
        self.conn.execute(
            """
            INSERT INTO repositories(
              repo_id, name, root_path, root_path_hash, vcs_type, remote_url_hash,
              default_branch, current_branch, registered_ts, last_seen_ts, active,
              index_status, latest_snapshot_id, capabilities_json, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'not_indexed', NULL, '{}', ?)
            """,
            (
                repo_id,
                display_name,
                str(root),
                path_hash(root),
                detect_vcs_type(root),
                detect_remote_url_hash(root),
                detect_default_branch(root),
                detect_current_branch(root),
                now,
                now,
                json.dumps(metadata, sort_keys=True),
            ),
        )
        self.conn.commit()
        return self.get_repo(repo_id)

    def unregister_repo(self, repo_id: str, *, keep_evidence: bool = True) -> RegisteredRepository:
        repo = self.get_repo(repo_id)
        if not keep_evidence:
            raise NotImplementedError("evidence deletion is out of scope for Phase 2")
        self.conn.execute("UPDATE repositories SET active=0, last_seen_ts=? WHERE repo_id=?", (_now_ts(), repo.repo_id))
        self.conn.commit()
        return self.get_repo(repo.repo_id)

    def get_repo(self, repo_id_or_name: str) -> RegisteredRepository:
        rows = self.conn.execute(
            "SELECT * FROM repositories WHERE repo_id = ? OR name = ? ORDER BY repo_id",
            (repo_id_or_name, repo_id_or_name),
        ).fetchall()
        if not rows:
            raise RepositoryNotFoundError(f"repository not found: {repo_id_or_name}")
        exact = [row for row in rows if row["repo_id"] == repo_id_or_name]
        if exact:
            return self._from_row(exact[0])
        if len(rows) > 1:
            raise DuplicateRepositoryError(f"repository name is ambiguous: {repo_id_or_name}")
        return self._from_row(rows[0])

    def list_repos(self, active_only: bool = True) -> list[RegisteredRepository]:
        where = "WHERE active=1" if active_only else ""
        return [self._from_row(row) for row in self.conn.execute(f"SELECT * FROM repositories {where} ORDER BY name, repo_id")]

    def update_repo_status(self, repo_id: str, status: str) -> None:
        self.get_repo(repo_id)
        self.conn.execute("UPDATE repositories SET index_status=?, last_seen_ts=? WHERE repo_id=?", (status, _now_ts(), repo_id))
        self.conn.commit()

    def set_latest_snapshot(self, repo_id: str, snapshot_id: str) -> None:
        self.get_repo(repo_id)
        self.conn.execute("UPDATE repositories SET latest_snapshot_id=?, last_seen_ts=? WHERE repo_id=?", (snapshot_id, _now_ts(), repo_id))
        self.conn.commit()

    def _from_row(self, row) -> RegisteredRepository:
        return RegisteredRepository(
            repo_id=row["repo_id"],
            name=row["name"],
            root_path=row["root_path"],
            root_path_hash=row["root_path_hash"],
            vcs_type=row["vcs_type"],
            remote_url_hash=row["remote_url_hash"],
            default_branch=row["default_branch"],
            current_branch=row["current_branch"],
            registered_ts=row["registered_ts"],
            last_seen_ts=row["last_seen_ts"],
            active=bool(row["active"]),
            index_status=row["index_status"],
            latest_snapshot_id=row["latest_snapshot_id"],
            capabilities=json.loads(row["capabilities_json"]),
            metadata=json.loads(row["metadata_json"]),
        )
