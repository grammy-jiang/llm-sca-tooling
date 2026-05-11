"""Contamination canary helpers."""

from __future__ import annotations

import difflib

from llm_sca_tooling.evaluation.models import (
    CanaryVerdict,
    ContaminationCanaryResult,
)

_SUSPECT_THRESHOLD = 0.85
_CONTAMINATED_THRESHOLD = 0.95


def basic_contamination_canary(
    *,
    eval_run_id: str,
    model_id: str,
    probe_instance_id: str | None = None,
    model_output: str | None = None,
    reference_text: str | None = None,
) -> ContaminationCanaryResult:
    """Compute a basic contamination verdict by string similarity.

    When both *model_output* and *reference_text* are provided the similarity
    is computed with :func:`difflib.SequenceMatcher`.  If either is absent the
    result falls back to :data:`CanaryVerdict.UNKNOWN`.
    """
    if model_output is not None and reference_text is not None:
        ratio = difflib.SequenceMatcher(
            None, model_output.strip(), reference_text.strip()
        ).ratio()
        if ratio >= _CONTAMINATED_THRESHOLD:
            verdict = CanaryVerdict.CONTAMINATED
        elif ratio >= _SUSPECT_THRESHOLD:
            verdict = CanaryVerdict.SUSPECT
        else:
            verdict = CanaryVerdict.CLEAN
        distance_raw = 1.0 - ratio
        diagnostics: list[dict[str, object]] = [
            {"code": "similarity_ratio", "value": round(ratio, 4)}
        ]
    else:
        verdict = CanaryVerdict.UNKNOWN
        distance_raw = None
        diagnostics = [{"code": "canary_inputs_unavailable"}]

    return ContaminationCanaryResult(
        canary_id="canary:basic:v1",
        eval_run_id=eval_run_id,
        model_id=model_id,
        probe_instance_id=probe_instance_id,
        memorisation_distance_raw=distance_raw,
        canary_verdict=verdict,
        diagnostics=diagnostics,
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
