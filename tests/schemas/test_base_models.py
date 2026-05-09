from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.schemas.base import canonical_json
from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    IndexStatus,
)
from llm_sca_tooling.schemas.provenance import (
    ArtifactRef,
    Provenance,
    RepoRef,
    SnapshotRef,
    SourceSpan,
)


def test_canonical_json_is_deterministic(repo: RepoRef) -> None:
    assert canonical_json({"b": 1, "a": repo.model_dump(mode="json")}).startswith(
        '{"a":'
    )


def test_source_span_rejects_invalid_line_range() -> None:
    with pytest.raises(ValidationError):
        SourceSpan(
            file_path="src/app.py",
            start_line=3,
            start_col=None,
            end_line=2,
            end_col=None,
        )


def test_source_span_rejects_absolute_path() -> None:
    with pytest.raises(ValidationError):
        SourceSpan(file_path="/tmp/app.py", start_line=1, end_line=1)


def test_snapshot_states_are_representable(repo: RepoRef) -> None:
    dirty = SnapshotRef(
        repo_id=repo.repo_id,
        git_sha=None,
        branch="main",
        worktree_snapshot_id="dirty:1",
        dirty=True,
        index_status=IndexStatus.PARTIAL,
        captured_ts="2026-05-09T00:00:00Z",
    )
    mixed = dirty.model_copy(update={"index_status": IndexStatus.MIXED})
    stale = dirty.model_copy(update={"index_status": IndexStatus.STALE})
    assert {dirty.index_status, mixed.index_status, stale.index_status} == {
        IndexStatus.PARTIAL,
        IndexStatus.MIXED,
        IndexStatus.STALE,
    }


def test_dirty_snapshot_requires_worktree_snapshot(repo: RepoRef) -> None:
    with pytest.raises(ValidationError):
        SnapshotRef(
            repo_id=repo.repo_id,
            git_sha=None,
            branch="main",
            worktree_snapshot_id=None,
            dirty=True,
            index_status=IndexStatus.PARTIAL,
            captured_ts="2026-05-09T00:00:00Z",
        )


def test_provenance_rejects_llm_hard_evidence(
    repo: RepoRef, snapshot: SnapshotRef
) -> None:
    with pytest.raises(ValidationError):
        Provenance(
            source_tool="llm",
            repo=repo,
            snapshot=snapshot,
            derivation=DerivationType.LLM,
            confidence=0.8,
            evidence_strength=EvidenceStrength.HARD_STATIC,
            created_ts="2026-05-09T00:00:00Z",
        )


def test_artifact_requires_redaction_status() -> None:
    with pytest.raises(ValidationError):
        ArtifactRef(artifact_id="art:1", kind="schema", uri="schemas/x.json")


def test_confidence_out_of_range_fails(repo: RepoRef, snapshot: SnapshotRef) -> None:
    with pytest.raises(ValidationError):
        Provenance(
            source_tool="parser",
            repo=repo,
            snapshot=snapshot,
            derivation=DerivationType.PARSER,
            confidence=1.1,
            evidence_strength=EvidenceStrength.HARD_STATIC,
            created_ts="2026-05-09T00:00:00Z",
        )
