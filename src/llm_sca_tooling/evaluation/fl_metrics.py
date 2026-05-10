"""Fault-localisation metric computation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from llm_sca_tooling.evaluation.models import (
    FLMetricInstanceResult,
    FLMetricsAggregator,
)


def compute_instance_fl_metrics(
    *,
    eval_run_id: str,
    instance_id: str,
    gold_files: Iterable[str],
    ranked_files: Iterable[str],
    budget_n: int | None = None,
    repair_correct: bool = False,
    language: str | None = None,
) -> FLMetricInstanceResult:
    gold = _normalise_unique(gold_files)
    ranked = _normalise_unique(ranked_files)
    if not gold:
        gold = ["<unknown>"]
    budget = max(1, budget_n or len(ranked) or len(gold))
    gold_count = len(gold)
    top1_window = ranked[:gold_count]
    top3_window = ranked[: max(3 * gold_count, 3)]
    topn_window = ranked[:budget]
    top1 = _contains_all(top1_window, gold)
    top3 = _contains_all(top3_window, gold)
    topn = _contains_all(topn_window, gold)
    return FLMetricInstanceResult(
        instance_id=instance_id,
        eval_run_id=eval_run_id,
        language=language,
        gold_files=gold,
        ranked_files=ranked,
        budget_n=budget,
        multi_file=gold_count > 1,
        fl_top1_correct=top1,
        fl_top3_correct=top3,
        fl_topN_correct=topn,
        repair_correct=repair_correct,
        fl_conditioned_repair_correct=(repair_correct and (top1 or top3)),
    )


def aggregate_fl_metrics(
    eval_run_id: str,
    results: Iterable[FLMetricInstanceResult],
    *,
    flaky_instance_ids: Iterable[str] = (),
) -> FLMetricsAggregator:
    excluded = set(flaky_instance_ids)
    included = [result for result in results if result.instance_id not in excluded]
    count = len(included)
    single = [result for result in included if not result.multi_file]
    multi = [result for result in included if result.multi_file]
    conditioned = [
        result
        for result in included
        if result.fl_top1_correct or result.fl_top3_correct
    ]
    by_language: dict[str, list[FLMetricInstanceResult]] = defaultdict(list)
    for result in included:
        by_language[result.language or "unknown"].append(result)
    return FLMetricsAggregator(
        eval_run_id=eval_run_id,
        instance_count=count,
        single_file_count=len(single),
        multi_file_count=len(multi),
        top1_rate=_rate(result.fl_top1_correct for result in included),
        top3_rate=_rate(result.fl_top3_correct for result in included),
        topN_rate=_rate(result.fl_topN_correct for result in included),
        repair_rate=_rate(result.repair_correct for result in included),
        fl_conditioned_repair_rate=_rate(
            result.repair_correct for result in conditioned
        ),
        per_instance_results=included,
        per_language_breakdown={
            language: {
                "instance_count": len(items),
                "top1_rate": _rate(item.fl_top1_correct for item in items),
                "top3_rate": _rate(item.fl_top3_correct for item in items),
                "topN_rate": _rate(item.fl_topN_correct for item in items),
            }
            for language, items in sorted(by_language.items())
        },
    )


def _normalise_unique(files: Iterable[str]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for file_path in files:
        normalised = file_path.strip().replace("\\", "/")
        if normalised.startswith("./"):
            normalised = normalised[2:]
        if normalised and normalised not in seen:
            seen.add(normalised)
            values.append(normalised)
    return values


def _contains_all(window: Iterable[str], gold: Iterable[str]) -> bool:
    window_set = set(window)
    return all(item in window_set for item in gold)


def _rate(flags: Iterable[bool]) -> float:
    values = list(flags)
    if not values:
        return 0.0
    return sum(1 for value in values if value) / len(values)
