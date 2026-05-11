"""Flaky-test detection helpers."""

from __future__ import annotations

import math

from llm_sca_tooling.evaluation.models import FlakyTestRecord

__all__ = ["detect_flakiness"]


def detect_flakiness(
    *,
    instance_id: str,
    eval_run_id: str,
    outcomes: list[bool],
    threshold: float = 0.3,
    known_flaky: bool = False,
) -> FlakyTestRecord:
    pass_count = sum(outcomes)
    fail_count = len(outcomes) - pass_count
    if known_flaky:
        entropy = 1.0
        method = "known_flaky_list"
    elif not outcomes:
        entropy = 0.0
        method = "deterministic_only"
    else:
        entropy = _binary_entropy(pass_count, fail_count)
        method = "rerun_entropy"
    flaky = known_flaky or entropy > threshold
    return FlakyTestRecord(
        instance_id=instance_id,
        eval_run_id=eval_run_id,
        flaky_flag=flaky,
        entropy_score=entropy,
        rerun_count=len(outcomes),
        pass_count=pass_count,
        fail_count=fail_count,
        detection_method=method,
        excluded_from_aggregate=flaky,
    )


def _binary_entropy(pass_count: int, fail_count: int) -> float:
    total = pass_count + fail_count
    if total == 0 or pass_count == 0 or fail_count == 0:
        return 0.0
    entropy = 0.0
    for count in (pass_count, fail_count):
        p = count / total
        entropy -= p * math.log2(p)
    return entropy
