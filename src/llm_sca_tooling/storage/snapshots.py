"""Snapshot ledger store."""

from __future__ import annotations

import json
from sqlite3 import Connection

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel
from llm_sca_tooling.schemas.enums import IndexStatus, SnapshotConsistency
from llm_sca_tooling.schemas.provenance import SnapshotRef
from llm_sca_tooling.storage.errors import SnapshotNotFoundError
from llm_sca_tooling.storage.ids import snapshot_id_for


class SnapshotRecord(StrictBaseModel):
    snapshot_id: str
    snapshot: SnapshotRef
    source_run_id: str | None = None
    source_event_id: str | None = None
    file_state_hash: str | None = None
    diagnostics: list[JsonObject] = Field(default_factory=list)
    metadata: JsonObject = Field(default_factory=dict)


class SnapshotMixResult(StrictBaseModel):
    snapshot_ids: list[str]
    snapshot_consistency: SnapshotConsistency
    mixed: bool
    reasons: list[str] = Field(default_factory=list)


class SnapshotStore:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def record_snapshot(
        self,
        snapshot: SnapshotRef,
        *,
        snapshot_id: str | None = None,
        source_run_id: str | None = None,
        source_event_id: str | None = None,
        file_state_hash: str | None = None,
        diagnostics: list[JsonObject] | None = None,
        metadata: JsonObject | None = None,
    ) -> SnapshotRecord:
        sid = snapshot_id or snapshot_id_for(snapshot, file_state_hash)
        self.conn.execute(
            """
            INSERT INTO snapshots(
              snapshot_id, repo_id, git_sha, branch, dirty, worktree_snapshot_id,
              index_status, captured_ts, source_run_id, source_event_id,
              file_state_hash, diagnostics_json, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_id) DO UPDATE SET
              index_status=excluded.index_status,
              diagnostics_json=excluded.diagnostics_json,
              metadata_json=excluded.metadata_json
            """,
            (
                sid,
                snapshot.repo_id,
                snapshot.git_sha,
                snapshot.branch,
                int(snapshot.dirty),
                snapshot.worktree_snapshot_id,
                snapshot.index_status.value,
                snapshot.captured_ts,
                source_run_id,
                source_event_id,
                file_state_hash,
                json.dumps(diagnostics or [], sort_keys=True),
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )
        self.conn.commit()
        return self.get_snapshot(sid)

    def get_snapshot(self, snapshot_id: str) -> SnapshotRecord:
        row = self.conn.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        if not row:
            raise SnapshotNotFoundError(f"snapshot not found: {snapshot_id}")
        return self._from_row(row)

    def get_latest_snapshot(self, repo_id: str, *, require_fresh: bool = False) -> SnapshotRecord | None:
        status_clause = "AND index_status='fresh'" if require_fresh else ""
        row = self.conn.execute(
            f"SELECT * FROM snapshots WHERE repo_id=? {status_clause} ORDER BY captured_ts DESC, snapshot_id DESC LIMIT 1",
            (repo_id,),
        ).fetchone()
        return None if row is None else self._from_row(row)

    def list_snapshots(self, repo_id: str, *, status: IndexStatus | None = None, limit: int | None = None) -> list[SnapshotRecord]:
        params: list[object] = [repo_id]
        where = "repo_id=?"
        if status is not None:
            where += " AND index_status=?"
            params.append(status.value)
        sql = f"SELECT * FROM snapshots WHERE {where} ORDER BY captured_ts DESC, snapshot_id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [self._from_row(row) for row in self.conn.execute(sql, params)]

    def mark_snapshot_status(self, snapshot_id: str, status: IndexStatus, diagnostics: list[JsonObject] | None = None) -> None:
        self.get_snapshot(snapshot_id)
        if diagnostics is None:
            self.conn.execute("UPDATE snapshots SET index_status=? WHERE snapshot_id=?", (status.value, snapshot_id))
        else:
            self.conn.execute(
                "UPDATE snapshots SET index_status=?, diagnostics_json=? WHERE snapshot_id=?",
                (status.value, json.dumps(diagnostics, sort_keys=True), snapshot_id),
            )
        self.conn.commit()

    def detect_mixed_snapshots(self, snapshot_ids: list[str]) -> SnapshotMixResult:
        records = [self.get_snapshot(snapshot_id) for snapshot_id in dict.fromkeys(snapshot_ids)]
        reasons: list[str] = []
        git_shas = {record.snapshot.git_sha for record in records if record.snapshot.git_sha}
        dirty_values = {record.snapshot.dirty for record in records}
        worktrees = {record.snapshot.worktree_snapshot_id for record in records if record.snapshot.worktree_snapshot_id}
        if len(git_shas) > 1:
            reasons.append("multiple git SHAs")
        if len(dirty_values) > 1:
            reasons.append("clean and dirty snapshots")
        if len(worktrees) > 1:
            reasons.append("multiple worktree snapshots")
        if any(record.snapshot.index_status == IndexStatus.MIXED for record in records):
            reasons.append("snapshot marked mixed")
        if reasons:
            consistency = SnapshotConsistency.MIXED
        elif any(record.snapshot.index_status == IndexStatus.STALE for record in records):
            consistency = SnapshotConsistency.STALE
        elif any(record.snapshot.dirty for record in records):
            consistency = SnapshotConsistency.DIRTY
        elif records:
            consistency = SnapshotConsistency.CLEAN
        else:
            consistency = SnapshotConsistency.UNKNOWN
        return SnapshotMixResult(snapshot_ids=[record.snapshot_id for record in records], snapshot_consistency=consistency, mixed=bool(reasons), reasons=reasons)

    def _from_row(self, row) -> SnapshotRecord:
        snapshot = SnapshotRef(
            repo_id=row["repo_id"],
            git_sha=row["git_sha"],
            branch=row["branch"],
            dirty=bool(row["dirty"]),
            worktree_snapshot_id=row["worktree_snapshot_id"],
            index_status=IndexStatus(row["index_status"]),
            captured_ts=row["captured_ts"],
        )
        return SnapshotRecord(
            snapshot_id=row["snapshot_id"],
            snapshot=snapshot,
            source_run_id=row["source_run_id"],
            source_event_id=row["source_event_id"],
            file_state_hash=row["file_state_hash"],
            diagnostics=json.loads(row["diagnostics_json"]),
            metadata=json.loads(row["metadata_json"]),
        )
