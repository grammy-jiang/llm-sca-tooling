"""Tests for the Incident schema."""

from __future__ import annotations

from pathlib import Path

import orjson
import pytest

from llm_sca_tooling.schemas.incidents import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    PromotionCandidate,
    PromotionTarget,
    ReviewState,
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
        source_tool="monitor",
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


def _incident(**kwargs: object) -> Incident:
    defaults: dict = {
        "incident_id": "inc:001",
        "severity": IncidentSeverity.P2,
        "title": "Test incident",
        "source_run_ids": ["run:test-001"],
        "provenance": _provenance(),
    }
    defaults.update(kwargs)
    return Incident(**defaults)  # type: ignore[arg-type]


def test_incident_round_trip() -> None:
    inc = _incident()
    dumped = inc.model_dump_json()
    loaded = Incident.model_validate_json(dumped)
    assert loaded.incident_id == "inc:001"
    assert loaded.status == IncidentStatus.open


def test_incident_defaults() -> None:
    inc = _incident()
    assert inc.status == IncidentStatus.open
    assert inc.evidence_links == []


def test_incident_requires_source_links() -> None:
    """Incidents with no source run or event IDs are rejected."""
    with pytest.raises(ValueError, match="source_run_id or source_event_id"):
        Incident(
            incident_id="inc:bad",
            severity=IncidentSeverity.P2,
            title="Bad",
            provenance=_provenance(),
        )


def test_incident_p0_with_description() -> None:
    inc = Incident(
        incident_id="inc:p0",
        severity=IncidentSeverity.P0,
        title="Critical failure",
        description="System compromised due to X",
        source_run_ids=["run:critical"],
        provenance=_provenance(),
    )
    assert inc.severity == IncidentSeverity.P0


def test_promotion_candidate_round_trip() -> None:
    candidate = PromotionCandidate(
        promotion_id="promo:001",
        source_run_id="run:123",
        target_type=PromotionTarget.memory,
        review_state=ReviewState.pending,
        lesson_summary="New lesson learned",
        owner="agent",
        provenance=_provenance(),
    )
    dumped = candidate.model_dump_json()
    loaded = PromotionCandidate.model_validate_json(dumped)
    assert loaded.promotion_id == "promo:001"
    assert loaded.review_state == ReviewState.pending


def test_promotion_approved_state() -> None:
    candidate = PromotionCandidate(
        promotion_id="promo:002",
        source_run_id="run:456",
        target_type=PromotionTarget.governance_policy,
        review_state=ReviewState.approved,
        lesson_summary="New policy added",
        owner="human",
        provenance=_provenance(),
    )
    assert candidate.review_state == ReviewState.approved


def test_incident_schema_file_exists() -> None:
    schema_path = SCHEMAS_DIR / "incident.schema.json"
    assert schema_path.exists(), "incident.schema.json not found in schemas/"
    schema = orjson.loads(schema_path.read_bytes())
    required = schema.get("required", [])
    assert "incident_id" in required
    assert "severity" in required
