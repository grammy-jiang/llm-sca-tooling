"""Tests for models / enums (smoke + extra=forbid)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.patch_review import models


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        models.DiffRecord(
            diff_id="d:1",
            diff_text="",
            diff_format="unified",
            changed_files=[],
            hunks=[],
            added_lines=0,
            removed_lines=0,
            net_lines=0,
            extra="x",  # type: ignore[call-arg]
        )


def test_axis_finding_round_trip() -> None:
    f = models.AxisFinding(
        axis=models.AuditAxis.SECURITY,
        findings=["x"],
        evidence_refs=[],
        risk_signals=[],
        confidence=models.ConfidenceLevel.ANALYSER,
        sampling_used=True,
        reviewer_id="r",
    )
    assert f.model_dump()["axis"] == "security"


def test_recommendation_enum_values() -> None:
    assert (
        models.Recommendation("merge-supporting")
        == models.Recommendation.MERGE_SUPPORTING
    )
    assert models.Recommendation("block") == models.Recommendation.BLOCK
    assert (
        models.Recommendation("review-required")
        == models.Recommendation.REVIEW_REQUIRED
    )
    assert models.Recommendation("unknown") == models.Recommendation.UNKNOWN


def test_risk_class_value_enum_values() -> None:
    assert models.RiskClassValue("safe") == models.RiskClassValue.SAFE
    assert models.RiskClassValue("vulnerable") == models.RiskClassValue.VULNERABLE
    assert (
        models.RiskClassValue("vulnerability-introducing")
        == models.RiskClassValue.VULNERABILITY_INTRODUCING
    )
