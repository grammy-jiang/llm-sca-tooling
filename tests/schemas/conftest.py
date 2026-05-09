from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    RedactionStatus,
)
from llm_sca_tooling.schemas.provenance import (
    ArtifactRef,
    Provenance,
    RepoRef,
    SnapshotRef,
)

TS = "2026-05-09T00:00:00Z"


@pytest.fixture
def repo() -> RepoRef:
    return RepoRef(repo_id="repo:demo", name="demo", default_branch="main")


@pytest.fixture
def snapshot(repo: RepoRef) -> SnapshotRef:
    return SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="0123456789abcdef0123456789abcdef01234567",
        branch="main",
        worktree_snapshot_id=None,
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )


@pytest.fixture
def provenance(repo: RepoRef, snapshot: SnapshotRef) -> Provenance:
    return Provenance(
        source_tool="tree-sitter",
        source_version="0.1",
        source_run_id="run:demo",
        source_event_id="event:run:demo:1",
        repo=repo,
        snapshot=snapshot,
        file="src/app.py",
        span=None,
        derivation=DerivationType.PARSER,
        confidence=1.0,
        evidence_strength=EvidenceStrength.HARD_STATIC,
        created_ts=TS,
        attributes={},
    )


@pytest.fixture
def artifact() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="art:demo",
        kind="schema",
        uri="schemas/graph.schema.json",
        sha256=None,
        size_bytes=None,
        media_type="application/schema+json",
        redaction_status=RedactionStatus.NOT_REQUIRED,
        created_ts=TS,
    )
