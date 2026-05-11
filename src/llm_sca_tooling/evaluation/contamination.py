"""Contamination canary helpers."""

from __future__ import annotations

from llm_sca_tooling.evaluation.models import ContaminationCanaryResult

__all__ = ["unknown_canary"]


def unknown_canary(
    *, eval_run_id: str, model_id: str, probe_instance_id: str
) -> ContaminationCanaryResult:
    return ContaminationCanaryResult(
        canary_id=f"canary:{eval_run_id}",
        eval_run_id=eval_run_id,
        model_id=model_id,
        probe_instance_id=probe_instance_id,
        memorisation_distance_raw=None,
        canary_verdict="unknown",
    )
