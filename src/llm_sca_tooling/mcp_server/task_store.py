"""Task persistence backed by operational records and artifacts."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from pydantic import Field

from llm_sca_tooling.indexing.hashing import hash_file, hash_text
from llm_sca_tooling.mcp_server.errors import (
    TaskAccessDenied,
    TaskExpired,
    TaskNotFound,
)
from llm_sca_tooling.mcp_server.serialization import to_jsonable
from llm_sca_tooling.mcp_server.task_ids import new_task_id
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, parse_utc_ts
from llm_sca_tooling.schemas.enums import ArtifactKind, RedactionStatus
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.storage.operations import OperationalRecord
from llm_sca_tooling.storage.workspace import WorkspaceStore, _now_ts


class TaskProgress(StrictBaseModel):
    stage: str
    message: str
    percent: float | None = None
    counts: JsonObject = Field(default_factory=dict)
    diagnostics_count: int = 0
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    ts: str = Field(default_factory=_now_ts)


class TaskRecord(StrictBaseModel):
    task_id: str
    tool_name: str
    status: str
    created_ts: str
    started_ts: str | None = None
    updated_ts: str
    completed_ts: str | None = None
    expires_ts: str
    ttl_seconds: int
    poll_interval_seconds: int
    progress: list[TaskProgress] = Field(default_factory=list)
    authorization_context_hash: str | None = None
    input_hash: str
    input_artifact_ref: ArtifactRef | None = None
    result_artifact_ref: ArtifactRef | None = None
    error: JsonObject | None = None
    run_id: str | None = None
    event_ids: list[str] = Field(default_factory=list)
    cancellation_requested: bool = False
    metadata: JsonObject = Field(default_factory=dict)


class TaskStore:
    def __init__(
        self,
        workspace: WorkspaceStore,
        *,
        default_ttl_seconds: int,
        poll_interval_seconds: int,
    ) -> None:
        self.workspace = workspace
        self.default_ttl_seconds = default_ttl_seconds
        self.poll_interval_seconds = poll_interval_seconds

    def create(
        self,
        tool_name: str,
        args: JsonObject,
        *,
        authorization_context_hash: str | None = None,
        ttl_seconds: int | None = None,
        metadata: JsonObject | None = None,
    ) -> TaskRecord:
        now = _now_ts()
        ttl = ttl_seconds or self.default_ttl_seconds
        expires = parse_utc_ts(now) + timedelta(seconds=ttl)
        record = TaskRecord(
            task_id=new_task_id(),
            tool_name=tool_name,
            status="queued",
            created_ts=now,
            updated_ts=now,
            expires_ts=expires.isoformat().replace("+00:00", "Z"),
            ttl_seconds=ttl,
            poll_interval_seconds=self.poll_interval_seconds,
            authorization_context_hash=authorization_context_hash,
            input_hash=hash_text(
                json.dumps(to_jsonable(args), sort_keys=True), length=32
            ),
            metadata=metadata or {},
        )
        self.save(record)
        return record

    def save(self, record: TaskRecord) -> TaskRecord:
        self.workspace.operations.record_operational_record(
            OperationalRecord(
                record_id=record.task_id,
                kind="mcp_task",
                payload=record.model_dump(mode="json"),
                status=record.status,
            )
        )
        return record

    def get(
        self, task_id: str, *, authorization_context_hash: str | None = None
    ) -> TaskRecord:
        row = self.workspace.conn.execute(
            "SELECT payload_json FROM operational_records WHERE record_id=? AND kind='mcp_task'",
            (task_id,),
        ).fetchone()
        if row is None:
            raise TaskNotFound(f"task not found: {task_id}")
        record = TaskRecord.model_validate(json.loads(row["payload_json"]))
        if (
            record.authorization_context_hash
            and record.authorization_context_hash != authorization_context_hash
        ):
            raise TaskAccessDenied("task authorization context mismatch")
        if parse_utc_ts(record.expires_ts) < parse_utc_ts(
            _now_ts()
        ) and record.status not in {"expired"}:
            record.status = "expired"
            record.updated_ts = _now_ts()
            self.save(record)
            raise TaskExpired(f"task expired: {task_id}")
        return record

    def list(self, *, allow: bool) -> list[TaskRecord]:
        if not allow:
            raise TaskAccessDenied("task listing is disabled by server policy")
        return [
            TaskRecord.model_validate(json.loads(row["payload_json"]))
            for row in self.workspace.conn.execute(
                "SELECT payload_json FROM operational_records WHERE kind='mcp_task' ORDER BY created_ts"
            )
        ]

    def recover_inflight(self) -> int:
        recovered = 0
        rows = self.workspace.conn.execute(
            "SELECT payload_json FROM operational_records WHERE kind='mcp_task'"
        ).fetchall()
        for row in rows:
            record = TaskRecord.model_validate(json.loads(row["payload_json"]))
            if record.status in {"queued", "running", "cancelling"}:
                record.status = "failed"
                record.error = {
                    "code": "server_restart_recovery",
                    "message": "task was in-flight during server startup",
                }
                record.completed_ts = _now_ts()
                record.updated_ts = record.completed_ts
                record.progress.append(
                    TaskProgress(
                        stage="recovery",
                        message="Marked in-flight task failed after restart",
                    )
                )
                self.save(record)
                recovered += 1
        return recovered

    def store_result(self, record: TaskRecord, result: Any) -> TaskRecord:
        root = self.workspace.artifact_root / "tasks"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{record.task_id.replace(':', '_')}_result.json"
        path.write_text(
            json.dumps(to_jsonable(result), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        ref = ArtifactRef(
            artifact_id=f"art:{record.task_id}:result",
            kind=ArtifactKind.REPORT,
            uri=str(path),
            sha256=hash_file(path),
            size_bytes=path.stat().st_size,
            media_type="application/json",
            redaction_status=RedactionStatus.REDACTED,
            created_ts=_now_ts(),
        )
        self.workspace.artifacts.record_artifact(
            ref, run_id=record.run_id, payload_path=path
        )
        record.result_artifact_ref = ref
        return record

    def load_result(self, record: TaskRecord) -> JsonObject:
        if record.result_artifact_ref is None:
            raise TaskNotFound(f"task result is unavailable: {record.task_id}")
        path = Path(record.result_artifact_ref.uri)
        if not path.exists() or hash_file(path) != record.result_artifact_ref.sha256:
            raise TaskNotFound(
                f"task result artifact missing or hash mismatch: {record.task_id}"
            )
        return json.loads(path.read_text(encoding="utf-8"))
