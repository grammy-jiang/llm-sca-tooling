"""Phase 18 calibration report computation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from llm_sca_tooling.release.models import CalibrationReport, CalibrationSample

__all__ = [
    "build_calibration_report",
    "expected_calibration_error",
    "macro_f1",
]

PATCH_ECE_THRESHOLD = 0.10
PATCH_MACRO_F1_THRESHOLD = 0.75
IMPL_ECE_THRESHOLD = 0.10
REPO_QA_FILE_LOC_THRESHOLD = 0.91
REPO_QA_BEHAVIOUR_THRESHOLD = 0.70
MEMORY_DELTA_THRESHOLD_PP = 3.0


def expected_calibration_error(
    samples: Iterable[CalibrationSample],
    *,
    bins: int = 10,
) -> float:
    """Compute weighted expected calibration error for labelled samples."""
    if bins <= 0:
        raise ValueError("bins must be positive")
    grouped: dict[int, list[CalibrationSample]] = defaultdict(list)
    all_samples = list(samples)
    if not all_samples:
        return 1.0
    for sample in all_samples:
        bucket = min(bins - 1, int(sample.predicted_probability * bins))
        grouped[bucket].append(sample)
    ece = 0.0
    for bucket_samples in grouped.values():
        accuracy = sum(sample.correct for sample in bucket_samples) / len(
            bucket_samples
        )
        confidence = sum(
            sample.predicted_probability for sample in bucket_samples
        ) / len(bucket_samples)
        ece += (len(bucket_samples) / len(all_samples)) * abs(accuracy - confidence)
    return ece


def macro_f1(samples: Iterable[CalibrationSample]) -> float:
    """Compute macro-F1 over labels present in predictions or gold labels."""
    all_samples = list(samples)
    if not all_samples:
        return 0.0
    labels = sorted(
        {
            label
            for sample in all_samples
            for label in (sample.predicted_label, sample.gold_label)
        }
    )
    scores: list[float] = []
    for label in labels:
        true_positive = sum(
            sample.predicted_label == label and sample.gold_label == label
            for sample in all_samples
        )
        false_positive = sum(
            sample.predicted_label == label and sample.gold_label != label
            for sample in all_samples
        )
        false_negative = sum(
            sample.predicted_label != label and sample.gold_label == label
            for sample in all_samples
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        scores.append(
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
    return sum(scores) / len(scores)


def build_calibration_report(
    *,
    eval_run_id: str,
    model_backend: str,
    harness_condition_id: str,
    patch_risk_samples: list[CalibrationSample],
    impl_check_samples: list[CalibrationSample],
    repo_qa_file_loc_accuracy: float,
    repo_qa_behaviour_tracing_accuracy: float,
    memory_her_eviction_delta_pp: float,
    rds_v2_summary: dict[str, object] | None = None,
) -> CalibrationReport:
    patch_by_family = _group_by_family(patch_risk_samples)
    impl_by_family = _group_by_family(impl_check_samples)
    patch_family_ece = {
        family: expected_calibration_error(samples)
        for family, samples in patch_by_family.items()
    }
    patch_family_f1 = {
        family: macro_f1(samples) for family, samples in patch_by_family.items()
    }
    impl_ece = {
        family: expected_calibration_error(samples)
        for family, samples in impl_by_family.items()
    }
    patch_ece = max(patch_family_ece.values(), default=1.0)
    patch_f1 = min(patch_family_f1.values(), default=0.0)
    patch_gate_passed = (
        bool(patch_family_ece)
        and all(value <= PATCH_ECE_THRESHOLD for value in patch_family_ece.values())
        and all(value >= PATCH_MACRO_F1_THRESHOLD for value in patch_family_f1.values())
    )
    impl_gate_passed = bool(impl_ece) and all(
        value <= IMPL_ECE_THRESHOLD for value in impl_ece.values()
    )
    return CalibrationReport(
        eval_run_id=eval_run_id,
        model_backend=model_backend,
        harness_condition_id=harness_condition_id,
        patch_risk_ece=patch_ece,
        patch_risk_macro_f1=patch_f1,
        patch_risk_calibration_family="+".join(sorted(patch_by_family)) or "none",
        patch_risk_gate_passed=patch_gate_passed,
        impl_check_ece_per_clause_family=impl_ece,
        impl_check_gate_passed=impl_gate_passed,
        repo_qa_file_loc_accuracy=repo_qa_file_loc_accuracy,
        repo_qa_behaviour_tracing_accuracy=repo_qa_behaviour_tracing_accuracy,
        repo_qa_behaviour_gate_passed=(
            repo_qa_file_loc_accuracy >= REPO_QA_FILE_LOC_THRESHOLD
            and repo_qa_behaviour_tracing_accuracy >= REPO_QA_BEHAVIOUR_THRESHOLD
        ),
        memory_her_eviction_delta_pp=memory_her_eviction_delta_pp,
        memory_ship_gate_passed=(
            memory_her_eviction_delta_pp >= MEMORY_DELTA_THRESHOLD_PP
        ),
        rds_v2_summary=dict(rds_v2_summary or {}),
    )


def _group_by_family(
    samples: Iterable[CalibrationSample],
) -> dict[str, list[CalibrationSample]]:
    grouped: dict[str, list[CalibrationSample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.family].append(sample)
    return dict(grouped)
