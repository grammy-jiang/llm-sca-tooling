"""Tests for the AIReadinessReport schema."""

from __future__ import annotations

from pathlib import Path

import orjson
import pytest

from llm_sca_tooling.schemas.governance import DriftClassification
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    Provenance,
    RepoRef,
    SnapshotRef,
)
from llm_sca_tooling.schemas.readiness import (
    AIReadinessReport,
    AxisScore,
    DriftFinding,
    HarnessStage,
    ReadinessAxis,
)

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas"
NOW = "2026-05-09T12:00:00Z"
REPO_ID = "repo:demo"


def _provenance() -> Provenance:
    return Provenance(
        source_tool="local-agent-harness",
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


def _repo_ref() -> RepoRef:
    return RepoRef(repo_id=REPO_ID, name="demo")


def _all_axis_scores(score: int = 2) -> list[AxisScore]:
    return [AxisScore(axis=ax, score=score) for ax in ReadinessAxis]


def test_readiness_report_round_trip() -> None:
    axes = _all_axis_scores(2)
    report = AIReadinessReport(
        readiness_report_id="rr:001",
        repo=_repo_ref(),
        stage=HarnessStage.S2,
        total_score=sum(a.score for a in axes),
        axis_scores=axes,
        provenance=_provenance(),
    )
    dumped = report.model_dump_json()
    loaded = AIReadinessReport.model_validate_json(dumped)
    assert loaded.readiness_report_id == "rr:001"
    assert loaded.stage == HarnessStage.S2


def test_readiness_report_total_must_match_axis_sum() -> None:
    axes = _all_axis_scores(3)
    with pytest.raises(ValueError):
        AIReadinessReport(
            readiness_report_id="rr:bad",
            repo=_repo_ref(),
            stage=HarnessStage.S1,
            total_score=99,  # wrong
            axis_scores=axes,
            provenance=_provenance(),
        )


def test_readiness_stage_threshold_s1() -> None:
    axes = _all_axis_scores(2)
    report = AIReadinessReport(
        readiness_report_id="rr:002",
        repo=_repo_ref(),
        stage=HarnessStage.S1,
        total_score=10,
        axis_scores=axes,
        provenance=_provenance(),
    )
    assert not report.meets_stage_threshold("S1->S2")  # requires total>=12


def test_readiness_stage_threshold_passes() -> None:
    axes = _all_axis_scores(3)
    report = AIReadinessReport(
        readiness_report_id="rr:003",
        repo=_repo_ref(),
        stage=HarnessStage.S2,
        total_score=15,
        axis_scores=axes,
        provenance=_provenance(),
    )
    assert report.meets_stage_threshold("S1->S2")


def test_drift_finding_model() -> None:
    finding = DriftFinding(
        drift_id="df:001",
        target_ref="AGENTS.md",
        classification=DriftClassification.stale,
        description="Missing managed section marker",
        blocks_release=False,
        provenance=_provenance(),
    )
    assert finding.classification == DriftClassification.stale


def test_readiness_schema_file_exists() -> None:
    schema_path = SCHEMAS_DIR / "readiness.schema.json"
    assert schema_path.exists(), "readiness.schema.json not found in schemas/"
    schema = orjson.loads(schema_path.read_bytes())
    required = schema.get("required", [])
    assert "readiness_report_id" in required
    assert "total_score" in required
