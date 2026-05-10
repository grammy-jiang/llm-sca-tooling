"""Contamination canary helpers."""

from __future__ import annotations

from llm_sca_tooling.evaluation.models import (
    CanaryVerdict,
    ContaminationCanaryResult,
)


def unknown_contamination_canary(
    *, eval_run_id: str, model_id: str, probe_instance_id: str | None = None
) -> ContaminationCanaryResult:
    return ContaminationCanaryResult(
        canary_id="canary:phase10:unknown",
        eval_run_id=eval_run_id,
        model_id=model_id,
        probe_instance_id=probe_instance_id,
        memorisation_distance_raw=None,
        canary_verdict=CanaryVerdict.UNKNOWN,
        diagnostics=[{"code": "canary_not_calibrated_phase10"}],
    )
