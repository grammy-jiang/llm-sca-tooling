"""Tests for governance, harness condition, readiness, and incident models."""

from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.governance import (
    HARD_CONSTRAINTS,
    DriftClassification,
    PermissionMode,
    ToolPermission,
)
from llm_sca_tooling.schemas.incidents import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    PromotionCandidate,
    PromotionTarget,
)
from llm_sca_tooling.schemas.provenance import RepoRef
from llm_sca_tooling.schemas.readiness import (
    AIReadinessReport,
    AxisScore,
    DriftFinding,
    HarnessStage,
    ReadinessAxis,
)

NOW = "2026-05-09T12:00:00Z"
REPO_ID = "repo:demo"


def test_hc1_through_hc6_exist() -> None:
    ids = {hc.constraint_id for hc in HARD_CONSTRAINTS}
    for hc_id in ("HC1", "HC2", "HC3", "HC4", "HC5", "HC6"):
        assert hc_id in ids


def test_tool_permission_read_mode() -> None:
    perm = ToolPermission(
        tool_name="Read",
        required_mode=PermissionMode.read,
    )
    assert perm.required_mode == PermissionMode.read


def test_drift_classification_relaxed_representable() -> None:
    assert DriftClassification.relaxed.value == "relaxed"


def test_drift_finding_valid(parser_provenance) -> None:
    df = DriftFinding(
        drift_id="d1",
        target_ref="AGENTS.md",
        classification=DriftClassification.relaxed,
        description="HC1 weakened",
        blocks_release=True,
        provenance=parser_provenance,
    )
    assert df.blocks_release is True


def test_readiness_report_axis_sum_mismatch_rejected(parser_provenance) -> None:
    with pytest.raises(ValueError, match="total_score"):
        AIReadinessReport(
            readiness_report_id="r1",
            repo=RepoRef(repo_id=REPO_ID),
            stage=HarnessStage.S0,
            total_score=20,  # wrong
            axis_scores=[
                AxisScore(axis=ReadinessAxis.agent_config, score=1),
                AxisScore(axis=ReadinessAxis.documentation, score=0),
                AxisScore(axis=ReadinessAxis.ci_cd, score=0),
                AxisScore(axis=ReadinessAxis.code_structure, score=0),
                AxisScore(axis=ReadinessAxis.security, score=0),
            ],
            provenance=parser_provenance,
        )


def test_readiness_report_threshold(parser_provenance) -> None:
    report = AIReadinessReport(
        readiness_report_id="r1",
        repo=RepoRef(repo_id=REPO_ID),
        stage=HarnessStage.S1,
        total_score=6,
        axis_scores=[
            AxisScore(axis=ReadinessAxis.agent_config, score=2),
            AxisScore(axis=ReadinessAxis.documentation, score=1),
            AxisScore(axis=ReadinessAxis.ci_cd, score=1),
            AxisScore(axis=ReadinessAxis.code_structure, score=1),
            AxisScore(axis=ReadinessAxis.security, score=1),
        ],
        provenance=parser_provenance,
    )
    assert report.meets_stage_threshold("S0->S1") is True
    assert report.meets_stage_threshold("S1->S2") is False


def test_incident_requires_source_links(parser_provenance) -> None:
    with pytest.raises(ValueError, match="source_run_id"):
        Incident(
            incident_id="inc:1",
            severity=IncidentSeverity.P0,
            title="loop",
            provenance=parser_provenance,
        )


def test_incident_valid(parser_provenance) -> None:
    inc = Incident(
        incident_id="inc:1",
        severity=IncidentSeverity.P1,
        title="out-of-scope write",
        source_run_ids=["run:001"],
        provenance=parser_provenance,
    )
    assert inc.status == IncidentStatus.open


def test_closed_incident_without_reviewer_rejected(parser_provenance) -> None:
    with pytest.raises(ValueError, match="reviewer"):
        Incident(
            incident_id="inc:1",
            severity=IncidentSeverity.P1,
            title="test",
            status=IncidentStatus.closed,
            source_run_ids=["run:1"],
            provenance=parser_provenance,
        )


def test_promotion_candidate_requires_source_run(parser_provenance) -> None:
    with pytest.raises(Exception):
        PromotionCandidate(
            promotion_id="p1",
            source_run_id="",  # empty string fails NonEmptyStr
            target_type=PromotionTarget.memory,
            lesson_summary="learned something",
            owner="alice",
            provenance=parser_provenance,
        )
