"""Patch-review workflow report assembly."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.evaluation.harness_condition import HarnessConditionSheet
from llm_sca_tooling.patch_review.four_agent_audit import run_four_axis_audit
from llm_sca_tooling.patch_review.merge_policy import recommend_merge
from llm_sca_tooling.patch_review.models import PatchReviewReport
from llm_sca_tooling.patch_review.operational_integration import (
    integrate_operational_result,
)
from llm_sca_tooling.patch_review.risk_classifier import classify_patch_risk


def run_patch_review(
    *,
    diff_text: str,
    run_id: str | None = None,
    sampling_supported: bool = False,
    sarif_before: list[dict[str, Any]] | None = None,
    sarif_after: list[dict[str, Any]] | None = None,
    before_failed: list[str] | None = None,
    after_failed: list[str] | None = None,
    run_events: list[str] | None = None,
) -> PatchReviewReport:
    risk, _vector, context = classify_patch_risk(
        diff_text=diff_text,
        sarif_before=sarif_before,
        sarif_after=sarif_after,
        before_failed=before_failed,
        after_failed=after_failed,
        run_events=run_events,
        run_id=run_id,
    )
    hcs = HarnessConditionSheet.create(run_id=run_id or context["diff"].diff_id)
    operational = integrate_operational_result(context["scope"])
    recommendation = recommend_merge(risk=risk, operational=operational)
    axes = run_four_axis_audit(
        risk=risk,
        evidence_ref=f"memory://patch/{context['diff'].diff_id}/evidence",
        sampling_supported=sampling_supported,
    )
    return PatchReviewReport(
        report_id=f"patch-review:{context['diff'].diff_id}",
        diff_id=context["diff"].diff_id,
        run_id=run_id,
        harness_condition_id=hcs.hcs_id,
        correctness_finding=axes["correctness"],
        security_finding=axes["security"],
        performance_finding=axes["performance"],
        compatibility_finding=axes["compatibility"],
        sarif_delta_ref=f"memory://patch/{context['diff'].diff_id}/sarif",
        test_delta_ref=f"memory://patch/{context['diff'].diff_id}/tests",
        interface_compat_result_ref=f"memory://patch/{context['diff'].diff_id}/interface",
        dryrun_prediction_ref=f"memory://patch/{context['diff'].diff_id}/dryrun",
        dryrun_mismatches=context["dryrun_mismatches"],
        scope_audit_result_ref=f"memory://patch/{context['diff'].diff_id}/scope",
        maintainability_gate_result_ref=f"memory://patch/{context['diff'].diff_id}/maintainability",
        patch_risk_result_ref=f"memory://patch/{context['diff'].diff_id}/risk",
        recommendation=recommendation,
        operational_verdict=operational.process_verdict,
        incident_links=operational.incident_ids,
        uncertainty=(
            "unknown calibration" if risk.risk_class.value == "unknown" else "heuristic"
        ),
        sampling_used=sampling_supported,
        fallback_mode=not sampling_supported,
    )
