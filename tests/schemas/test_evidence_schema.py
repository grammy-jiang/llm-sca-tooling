"""Tests for the EvidenceBundle schema."""

from __future__ import annotations

from pathlib import Path

import orjson

from llm_sca_tooling.schemas.evidence import (
    EvidenceBundle,
    EvidenceItem,
    EvidenceSupport,
    MissingEvidence,
    SnapshotConsistency,
    StaleEvidence,
)
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    Provenance,
    RepoRef,
    SnapshotRef,
)

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas"
NOW = "2026-05-09T12:00:00Z"
REPO_ID = "repo:demo"


def _provenance() -> Provenance:
    return Provenance(
        source_tool="tree-sitter",
        source_version="0.22",
        repo=RepoRef(repo_id=REPO_ID, name="demo"),
        snapshot=SnapshotRef(
            repo_id=REPO_ID,
            git_sha="0123456789abcdef0123456789abcdef01234567",
            branch="main",
            dirty=False,
            index_status=IndexStatus.fresh,
            captured_ts=NOW,
        ),
        derivation=DerivationType.parser,
        confidence=1.0,
        evidence_strength=EvidenceStrength.hard_static,
        created_ts=NOW,
    )


def test_evidence_bundle_round_trip() -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle:001",
        subject_ref="func:foo",
        created_ts=NOW,
        provenance=_provenance(),
    )
    dumped = bundle.model_dump_json()
    loaded = EvidenceBundle.model_validate_json(dumped)
    assert loaded.bundle_id == bundle.bundle_id
    assert loaded.snapshot_consistency == SnapshotConsistency.unknown


def test_evidence_bundle_with_items() -> None:
    item = EvidenceItem(
        evidence_id="ev:001",
        kind="static_analysis",
        supports=EvidenceSupport.supports,
        strength=EvidenceStrength.hard_static,
        confidence=0.95,
        provenance=_provenance(),
    )
    bundle = EvidenceBundle(
        bundle_id="bundle:002",
        subject_ref="func:bar",
        evidence_items=[item],
        created_ts=NOW,
        provenance=_provenance(),
    )
    assert not bundle.is_only_soft_llm
    assert bundle.weakest_strength() == EvidenceStrength.hard_static


def test_evidence_bundle_empty_is_soft_llm() -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle:003",
        subject_ref="func:baz",
        created_ts=NOW,
        provenance=_provenance(),
    )
    assert bundle.is_only_soft_llm
    assert bundle.weakest_strength() == EvidenceStrength.soft_llm


def test_missing_evidence_model() -> None:
    m = MissingEvidence(
        evidence_id="ev:missing",
        required_for="verdict",
        description="Test coverage absent",
        forces_unknown=True,
    )
    assert m.forces_unknown is True


def test_stale_evidence_model() -> None:
    s = StaleEvidence(
        evidence_id="ev:stale",
        reason="Snapshot is 30 days old",
        stale_refs=["snap:old"],
        forces_unknown=True,
    )
    assert "snap:old" in s.stale_refs


def test_evidence_schema_file_exists_and_valid() -> None:
    schema_path = SCHEMAS_DIR / "evidence.schema.json"
    assert schema_path.exists(), "evidence.schema.json not found in schemas/"
    schema = orjson.loads(schema_path.read_bytes())
    assert "$defs" in schema or "properties" in schema
    assert schema.get("title") == "EvidenceBundle"
