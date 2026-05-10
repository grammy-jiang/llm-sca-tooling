"""Flaky-test metadata and entropy detection."""

from __future__ import annotations

import math
from collections.abc import Iterable

from llm_sca_tooling.evaluation.models import FlakyTestRecord


def entropy_score(pass_count: int, fail_count: int) -> float:
    total = pass_count + fail_count
    if total == 0 or pass_count == 0 or fail_count == 0:
        return 0.0
    probabilities = (pass_count / total, fail_count / total)
    return -sum(probability * math.log2(probability) for probability in probabilities)


def detect_flaky_test(
    *,
    eval_run_id: str,
    instance_id: str,
    outcomes: Iterable[bool],
    method: str = "rerun_entropy",
    threshold: float = 0.3,
    known_flaky: bool = False,
) -> FlakyTestRecord:
    values = list(outcomes)
    pass_count = sum(1 for value in values if value)
    fail_count = sum(1 for value in values if not value)
    score = entropy_score(pass_count, fail_count)
    flaky = known_flaky or score > threshold
    return FlakyTestRecord(
        instance_id=instance_id,
        eval_run_id=eval_run_id,
        flaky_flag=flaky,
        entropy_score=score,
        rerun_count=len(values),
        pass_count=pass_count,
        fail_count=fail_count,
        detection_method="known_flaky_list" if known_flaky else method,
        excluded_from_aggregate=flaky,
    )
