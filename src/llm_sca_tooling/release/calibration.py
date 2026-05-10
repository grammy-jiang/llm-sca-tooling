"""Calibration report computation."""

from __future__ import annotations

import uuid
from collections import defaultdict

from llm_sca_tooling.release.models import CalibrationReport
from llm_sca_tooling.schemas.base import JsonObject


def expected_calibration_error(
    predictions: list[JsonObject], *, bins: int = 10
) -> float:
    if not predictions:
        return 1.0
    buckets: dict[int, list[JsonObject]] = defaultdict(list)
    for item in predictions:
        confidence = float(item.get("confidence", 0.0))
        bucket = min(bins - 1, int(confidence * bins))
        buckets[bucket].append(item)
    total = len(predictions)
    ece = 0.0
    for bucket_items in buckets.values():
        avg_conf = sum(
            float(item.get("confidence", 0.0)) for item in bucket_items
        ) / len(bucket_items)
        accuracy = sum(1.0 for item in bucket_items if bool(item.get("correct"))) / len(
            bucket_items
        )
        ece += (len(bucket_items) / total) * abs(avg_conf - accuracy)
    return ece


def macro_f1(predictions: list[JsonObject]) -> float:
    if not predictions:
        return 0.0
    labels = sorted(
        {str(item.get("label", "")) for item in predictions}
        | {str(item.get("predicted", "")) for item in predictions}
    )
    scores: list[float] = []
    for label in labels:
        tp = sum(
            1
            for item in predictions
            if item.get("label") == label and item.get("predicted") == label
        )
        fp = sum(
            1
            for item in predictions
            if item.get("label") != label and item.get("predicted") == label
        )
        fn = sum(
            1
            for item in predictions
            if item.get("label") == label and item.get("predicted") != label
        )
        denom = (2 * tp) + fp + fn
        scores.append(0.0 if denom == 0 else (2 * tp) / denom)
    return sum(scores) / len(scores)


def build_calibration_report(
    *,
    eval_run_id: str,
    model_backend: str,
    harness_condition_id: str,
    patch_risk_predictions: list[JsonObject],
    impl_check_predictions_by_family: dict[str, list[JsonObject]],
    repo_qa_file_loc_accuracy: float,
    repo_qa_behaviour_tracing_accuracy: float,
    memory_delta_pp: float,
    family: str = "default",
) -> CalibrationReport:
    patch_ece = expected_calibration_error(patch_risk_predictions)
    patch_f1 = macro_f1(patch_risk_predictions)
    impl_ece = {
        name: expected_calibration_error(items)
        for name, items in impl_check_predictions_by_family.items()
    }
    return CalibrationReport(
        report_id=f"calibration:{uuid.uuid4().hex}",
        eval_run_id=eval_run_id,
        model_backend=model_backend,
        harness_condition_id=harness_condition_id,
        patch_risk_ece=patch_ece,
        patch_risk_macro_f1=patch_f1,
        patch_risk_calibration_family=family,
        patch_risk_gate_passed=patch_ece <= 0.10 and patch_f1 >= 0.75,
        impl_check_ece_per_clause_family=impl_ece,
        impl_check_gate_passed=bool(impl_ece)
        and all(value <= 0.10 for value in impl_ece.values()),
        repo_qa_file_loc_accuracy=repo_qa_file_loc_accuracy,
        repo_qa_behaviour_tracing_accuracy=repo_qa_behaviour_tracing_accuracy,
        repo_qa_behaviour_gate_passed=repo_qa_file_loc_accuracy >= 0.91
        and repo_qa_behaviour_tracing_accuracy >= 0.70,
        memory_her_eviction_delta_pp=memory_delta_pp,
        memory_ship_gate_passed=memory_delta_pp >= 3.0,
        rds_v2_summary={"axes": 6, "calibrated": True},
    )
