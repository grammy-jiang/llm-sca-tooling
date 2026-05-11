"""Remaining-risk notes."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.models import (
    BuildTestResult,
    RemainingRiskNote,
    SARIFDeltaVerificationResult,
)


def make_remaining_risk_note(
    *,
    alert_id: str,
    sarif: SARIFDeltaVerificationResult,
    build_tests: BuildTestResult,
    vulnerability_class: bool,
    poc_plus_available: bool = False,
) -> RemainingRiskNote:
    if (
        sarif.success
        and build_tests.test_run_status == "passed"
        and (not vulnerability_class or poc_plus_available)
    ):
        level = "none"
        desc = "SARIF and tests passed."
    elif sarif.success:
        level = "medium" if vulnerability_class else "low"
        desc = "Alert disappeared but PoC+ or path coverage is incomplete."
    else:
        level = "high"
        desc = sarif.block_reason or "repair not verified"
    return RemainingRiskNote(
        alert_id=alert_id,
        risk_level=level,
        risk_description=desc,
        verification_method_used="sarif-delta+build-tests",
        unverified_paths=[] if level == "none" else ["dynamic-paths"],
        recommended_followup=(
            "none" if level == "none" else "manual review or dynamic trace"
        ),
    )
