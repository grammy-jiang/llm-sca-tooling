"""Raw and compressed trace artefact writers."""

from __future__ import annotations

import hashlib
from pathlib import Path

import orjson

from llm_sca_tooling.schemas.enums import ArtifactKind, RedactionStatus
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.storage.artifacts import ArtifactStore
from llm_sca_tooling.storage.workspace import _now_ts
from llm_sca_tooling.traces.models import CompressedTrace, RawTraceArtefact


def trace_run_dir(artifact_root: Path, trace_run_id: str) -> Path:
    path = artifact_root / "traces" / trace_run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_model_json(path: Path, model: RawTraceArtefact | CompressedTrace) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        orjson.dumps(model.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS) + b"\n"
    )
    return path


def artifact_ref_for_path(
    *,
    artifact_id: str,
    path: Path,
    kind: ArtifactKind,
    media_type: str,
) -> ArtifactRef:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ArtifactRef(
        artifact_id=artifact_id,
        kind=kind,
        uri=str(path),
        sha256=digest,
        size_bytes=path.stat().st_size,
        media_type=media_type,
        redaction_status=RedactionStatus.REDACTED,
        created_ts=_now_ts(),
    )


def record_artifact(
    store: ArtifactStore | None,
    ref: ArtifactRef,
    *,
    repo_id: str | None = None,
    run_id: str | None = None,
    payload_path: Path | None = None,
) -> ArtifactRef:
    if store is None:
        return ref
    return store.record_artifact(
        ref, repo_id=repo_id, run_id=run_id, payload_path=payload_path
    )
