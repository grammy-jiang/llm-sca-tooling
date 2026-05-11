"""Shared fixtures for schema tests."""

from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    Provenance,
    RepoRef,
    SnapshotRef,
    SourceSpan,
)

NOW = "2026-05-09T12:00:00Z"
REPO_ID = "repo:demo"


@pytest.fixture()
def repo_ref() -> RepoRef:
    return RepoRef(repo_id=REPO_ID, name="demo", default_branch="main")


@pytest.fixture()
def snapshot_ref() -> SnapshotRef:
    return SnapshotRef(
        repo_id=REPO_ID,
        git_sha="0123456789abcdef0123456789abcdef01234567",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )


@pytest.fixture()
def source_span() -> SourceSpan:
    return SourceSpan(
        file_path="src/app.py",
        start_line=1,
        end_line=120,
        encoding="utf-8",
    )


@pytest.fixture()
def parser_provenance(repo_ref: RepoRef, snapshot_ref: SnapshotRef) -> Provenance:
    return Provenance(
        source_tool="tree-sitter",
        source_version="0.22",
        repo=repo_ref,
        snapshot=snapshot_ref,
        derivation=DerivationType.parser,
        confidence=1.0,
        evidence_strength=EvidenceStrength.hard_static,
        created_ts=NOW,
    )


@pytest.fixture()
def llm_provenance(repo_ref: RepoRef, snapshot_ref: SnapshotRef) -> Provenance:
    return Provenance(
        source_tool="claude-sonnet-4-6",
        repo=repo_ref,
        snapshot=snapshot_ref,
        derivation=DerivationType.llm,
        confidence=0.8,
        evidence_strength=EvidenceStrength.soft_llm,
        created_ts=NOW,
    )
