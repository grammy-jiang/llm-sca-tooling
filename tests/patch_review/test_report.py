"""Tests for end-to-end report orchestration."""

from __future__ import annotations

import asyncio

from llm_sca_tooling.patch_review.report import classify_patch_risk, run_patch_review


def _run(coro):
    return asyncio.run(coro)


def test_run_patch_review_safe(safe_diff: str) -> None:
    report, sheet = _run(run_patch_review(diff=safe_diff, run_id="r1"))
    assert report.report_id.startswith("patch-review:")
    assert sheet.hcs_id.startswith("hcs:")
    assert report.harness_condition_id == sheet.hcs_id
    assert not report.sampling_used
    assert report.fallback_mode


def test_run_patch_review_blocks_on_critical(safe_diff: str) -> None:
    report, _ = _run(
        run_patch_review(
            diff=safe_diff,
            run_id="r1",
            sarif_appeared=[
                {"alert_id": "a", "severity": "critical", "rule_id": "py/sql-injection"}
            ],
        )
    )
    assert report.recommendation.value == "block"


def test_run_patch_review_with_sampling_client(safe_diff: str) -> None:
    from llm_sca_tooling.patch_review.sampling_integration import FallbackSamplingClient

    class FakeSampling(FallbackSamplingClient):
        available = True

    report, _ = _run(
        run_patch_review(
            diff=safe_diff,
            run_id="r1",
            sampling_enabled=True,
            sampling_client=FakeSampling(),
        )
    )
    assert report.sampling_used
    assert all(
        f.sampling_used
        for f in (
            report.correctness_finding,
            report.security_finding,
            report.performance_finding,
            report.compatibility_finding,
        )
    )


def test_run_patch_review_dryrun_mismatch_degrades(safe_diff: str) -> None:
    report, _ = _run(
        run_patch_review(
            diff=safe_diff,
            run_id="r1",
            actual_files_changed=["unexpected.py"],
        )
    )
    assert any(m.diff_id for m in report.dryrun_mismatches)
    assert "dryrun_mismatch_detected" in report.uncertainty


def test_classify_patch_risk_returns_dict(safe_diff: str) -> None:
    result = _run(classify_patch_risk(diff=safe_diff, run_id="r1"))
    assert "risk_result" in result
    assert "feature_vector" in result
    assert "diff" in result


def test_classify_patch_risk_with_sarif_block(safe_diff: str) -> None:
    result = _run(
        classify_patch_risk(
            diff=safe_diff,
            run_id="r1",
            sarif_appeared=[
                {"alert_id": "a", "severity": "critical", "rule_id": "py/x"}
            ],
        )
    )
    assert result["risk_result"]["policy_action"] == "block"
