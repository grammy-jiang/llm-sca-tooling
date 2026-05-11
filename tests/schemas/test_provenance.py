"""Tests for provenance, snapshot, span, and artefact models."""

from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.provenance import (
    ArtifactKind,
    ArtifactRef,
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    PolicyAction,
    Provenance,
    RedactionStatus,
    RepoRef,
    SnapshotRef,
    SourceSpan,
)

NOW = "2026-05-09T12:00:00Z"
REPO_ID = "repo:demo"


# ---------------------------------------------------------------------------
# EvidenceStrength ordering
# ---------------------------------------------------------------------------


def test_evidence_strength_ordering() -> None:
    assert EvidenceStrength.hard_static > EvidenceStrength.soft_llm
    assert EvidenceStrength.soft_llm < EvidenceStrength.hard_static
    assert EvidenceStrength.hard_dynamic > EvidenceStrength.calibrated_model
    assert EvidenceStrength.structured_repository >= EvidenceStrength.calibrated_model


def test_evidence_strength_min() -> None:
    items = [
        EvidenceStrength.hard_static,
        EvidenceStrength.soft_llm,
        EvidenceStrength.calibrated_model,
    ]
    assert min(items) == EvidenceStrength.soft_llm


def test_evidence_strength_max() -> None:
    items = [EvidenceStrength.hard_static, EvidenceStrength.soft_llm]
    assert max(items) == EvidenceStrength.hard_static


# ---------------------------------------------------------------------------
# SnapshotRef
# ---------------------------------------------------------------------------


def test_snapshot_ref_valid() -> None:
    s = SnapshotRef(
        repo_id=REPO_ID,
        git_sha="abc123",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )
    assert s.repo_id == REPO_ID


def test_snapshot_ref_dirty_worktree() -> None:
    s = SnapshotRef(
        repo_id=REPO_ID,
        worktree_snapshot_id="snap:abc",
        dirty=True,
        index_status=IndexStatus.partial,
        captured_ts=NOW,
    )
    assert s.dirty is True


def test_snapshot_ref_mixed_index_status() -> None:
    s = SnapshotRef(
        repo_id=REPO_ID,
        index_status=IndexStatus.mixed,
        captured_ts=NOW,
    )
    assert s.index_status == IndexStatus.mixed


# ---------------------------------------------------------------------------
# SourceSpan
# ---------------------------------------------------------------------------


def test_source_span_valid() -> None:
    s = SourceSpan(file_path="src/foo.py", start_line=1, end_line=10)
    assert s.start_line == 1


def test_source_span_end_before_start_rejected() -> None:
    with pytest.raises(Exception):
        SourceSpan(file_path="src/foo.py", start_line=10, end_line=5)


def test_source_span_single_line() -> None:
    s = SourceSpan(file_path="src/foo.py", start_line=5, end_line=5)
    assert s.end_line == s.start_line


# ---------------------------------------------------------------------------
# ArtifactRef
# ---------------------------------------------------------------------------


def test_artifact_ref_requires_redaction_status() -> None:
    with pytest.raises(Exception):
        ArtifactRef(
            artifact_id="art:1",
            kind=ArtifactKind.sarif,
            uri="file://x.sarif",
        )  # type: ignore[call-arg]


def test_artifact_ref_valid() -> None:
    a = ArtifactRef(
        artifact_id="art:1",
        kind=ArtifactKind.sarif,
        uri="file://x.sarif",
        redaction_status=RedactionStatus.not_required,
    )
    assert a.artifact_id == "art:1"


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def _make_prov(
    derivation: DerivationType = DerivationType.parser,
    strength: EvidenceStrength = EvidenceStrength.hard_static,
) -> Provenance:
    return Provenance(
        source_tool="tool",
        repo=RepoRef(repo_id=REPO_ID),
        snapshot=SnapshotRef(repo_id=REPO_ID, captured_ts=NOW),
        derivation=derivation,
        confidence=1.0,
        evidence_strength=strength,
        created_ts=NOW,
    )


def test_provenance_valid() -> None:
    p = _make_prov()
    assert p.source_tool == "tool"


def test_llm_hard_static_rejected() -> None:
    with pytest.raises(ValueError, match="cannot claim"):
        _make_prov(DerivationType.llm, EvidenceStrength.hard_static)


def test_llm_hard_dynamic_rejected() -> None:
    with pytest.raises(ValueError, match="cannot claim"):
        _make_prov(DerivationType.llm, EvidenceStrength.hard_dynamic)


def test_llm_soft_llm_allowed() -> None:
    p = _make_prov(DerivationType.llm, EvidenceStrength.soft_llm)
    assert p.derivation == DerivationType.llm


def test_provenance_repo_id_mismatch_rejected() -> None:
    with pytest.raises(ValueError, match="repo_id"):
        Provenance(
            source_tool="tool",
            repo=RepoRef(repo_id="repo:A"),
            snapshot=SnapshotRef(repo_id="repo:B", captured_ts=NOW),
            derivation=DerivationType.parser,
            confidence=1.0,
            evidence_strength=EvidenceStrength.hard_static,
            created_ts=NOW,
        )


def test_confidence_out_of_range_rejected() -> None:
    with pytest.raises(Exception):
        _make_prov = Provenance(
            source_tool="tool",
            repo=RepoRef(repo_id=REPO_ID),
            snapshot=SnapshotRef(repo_id=REPO_ID, captured_ts=NOW),
            derivation=DerivationType.parser,
            confidence=1.5,
            evidence_strength=EvidenceStrength.hard_static,
            created_ts=NOW,
        )


def test_policy_action_enum_values() -> None:
    for v in PolicyAction:
        assert isinstance(v.value, str)
