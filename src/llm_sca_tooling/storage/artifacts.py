"""Artifact registry store."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from sqlite3 import Connection

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.storage.errors import ArtifactNotFoundError
from llm_sca_tooling.storage.workspace import _now_ts


class ArtifactHashResult(StrictBaseModel):
    artifact_id: str
    passed: bool
    expected_sha256: str | None
    actual_sha256: str | None
    diagnostic: str | None = None


class ArtifactStore:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def record_artifact(
        self,
        ref: ArtifactRef,
        *,
        repo_id: str | None = None,
        run_id: str | None = None,
        payload_path: str | Path | None = None,
    ) -> ArtifactRef:
        ref = ArtifactRef.model_validate(ref.model_dump(mode="python"))
        metadata: JsonObject = {}
        if payload_path is not None:
            metadata["payload_path"] = str(Path(payload_path))
        self.conn.execute(
            """
            INSERT INTO artifacts(artifact_id, repo_id, run_id, kind, uri, sha256, size_bytes, media_type, redaction_status, created_ts, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(artifact_id) DO UPDATE SET
              repo_id=excluded.repo_id,
              run_id=excluded.run_id,
              sha256=excluded.sha256,
              size_bytes=excluded.size_bytes,
              media_type=excluded.media_type,
              redaction_status=excluded.redaction_status,
              metadata_json=excluded.metadata_json
            """,
            (
                ref.artifact_id,
                repo_id,
                run_id,
                ref.kind.value,
                ref.uri,
                ref.sha256,
                ref.size_bytes,
                ref.media_type,
                ref.redaction_status.value,
                ref.created_ts or _now_ts(),
                json.dumps(metadata, sort_keys=True),
            ),
        )
        self.conn.commit()
        return self.get_artifact(ref.artifact_id)

    def get_artifact(self, artifact_id: str) -> ArtifactRef:
        row = self.conn.execute(
            "SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)
        ).fetchone()
        if not row:
            raise ArtifactNotFoundError(f"artifact not found: {artifact_id}")
        return self._from_row(row)

    def list_artifacts(
        self,
        repo_id: str | None = None,
        run_id: str | None = None,
        kind: str | None = None,
    ) -> list[ArtifactRef]:
        clauses: list[str] = []
        params: list[object] = []
        if repo_id is not None:
            clauses.append("repo_id=?")
            params.append(repo_id)
        if run_id is not None:
            clauses.append("run_id=?")
            params.append(run_id)
        if kind is not None:
            clauses.append("kind=?")
            params.append(kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return [
            self._from_row(row)
            for row in self.conn.execute(
                f"SELECT * FROM artifacts {where} ORDER BY created_ts, artifact_id",
                params,
            )
        ]

    def verify_artifact_hash(self, artifact_id: str) -> ArtifactHashResult:
        row = self.conn.execute(
            "SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)
        ).fetchone()
        if not row:
            raise ArtifactNotFoundError(f"artifact not found: {artifact_id}")
        expected = row["sha256"]
        metadata = json.loads(row["metadata_json"])
        path = metadata.get("payload_path") or row["uri"]
        payload_path = Path(path)
        if not payload_path.exists():
            return ArtifactHashResult(
                artifact_id=artifact_id,
                passed=False,
                expected_sha256=expected,
                actual_sha256=None,
                diagnostic="artifact file missing",
            )
        actual = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        return ArtifactHashResult(
            artifact_id=artifact_id,
            passed=(expected == actual),
            expected_sha256=expected,
            actual_sha256=actual,
        )

    def _from_row(self, row) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=row["artifact_id"],
            kind=row["kind"],
            uri=row["uri"],
            sha256=row["sha256"],
            size_bytes=row["size_bytes"],
            media_type=row["media_type"],
            redaction_status=row["redaction_status"],
            created_ts=row["created_ts"],
        )
