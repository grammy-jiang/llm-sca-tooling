from __future__ import annotations

import hashlib

from llm_sca_tooling.schemas.provenance import ArtifactRef
from tests.storage.conftest import artifact_ref, run_record


def test_artifact_record_and_hash_verification(workspace, tmp_path, registered_repo) -> None:
    payload = tmp_path / "artifact.txt"
    payload.write_text("hello", encoding="utf-8")
    ref = workspace.artifacts.record_artifact(artifact_ref(payload), repo_id=registered_repo.repo_id, payload_path=payload)
    assert workspace.artifacts.get_artifact(ref.artifact_id).sha256 == ref.sha256
    assert workspace.artifacts.verify_artifact_hash(ref.artifact_id).passed
    payload.write_text("changed", encoding="utf-8")
    assert not workspace.artifacts.verify_artifact_hash(ref.artifact_id).passed


def test_missing_artifact_file_diagnostic(workspace, tmp_path) -> None:
    payload = tmp_path / "missing.txt"
    ref = ArtifactRef(
        artifact_id="art:missing",
        kind="log",
        uri=str(payload),
        sha256=hashlib.sha256(b"missing").hexdigest(),
        size_bytes=7,
        media_type="text/plain",
        redaction_status="redacted",
        created_ts="2026-05-09T00:00:00Z",
    )
    workspace.artifacts.record_artifact(ref, payload_path=payload)
    result = workspace.artifacts.verify_artifact_hash(ref.artifact_id)
    assert not result.passed
    assert result.diagnostic == "artifact file missing"


def test_list_artifacts_by_repo_run_kind(workspace, tmp_path, registered_repo, repo_ref) -> None:
    workspace.operations.create_run(run_record(repo_ref))
    payload = tmp_path / "artifact.txt"
    payload.write_text("hello", encoding="utf-8")
    workspace.artifacts.record_artifact(artifact_ref(payload), repo_id=registered_repo.repo_id, run_id="run:demo", payload_path=payload)
    assert workspace.artifacts.list_artifacts(repo_id=registered_repo.repo_id)
    assert workspace.artifacts.list_artifacts(run_id="run:demo")
    assert workspace.artifacts.list_artifacts(kind="log")
