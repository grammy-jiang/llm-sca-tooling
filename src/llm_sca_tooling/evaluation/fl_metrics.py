"""Fault-localisation metric aggregation."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.evaluation.benchmark_adapter import SuspectRecord
from llm_sca_tooling.evaluation.models import EvalInstanceResult, StrictEvalModel

__all__ = ["FLMetricsAggregator", "score_instance"]


class FLMetricsAggregator(StrictEvalModel):
    eval_run_id: str
    instance_count: int
    single_file_count: int
    multi_file_count: int
    top1_rate: float
    top3_rate: float
    topN_rate: float  # noqa: N815 - external eval schema field
    fl_conditioned_repair_rate: float
    per_instance_results: list[dict[str, object]] = Field(default_factory=list)
    per_language_breakdown: dict[str, dict[str, float]] = Field(default_factory=dict)

    @classmethod
    def from_instances(
        cls, eval_run_id: str, results: list[EvalInstanceResult]
    ) -> FLMetricsAggregator:
        included = [result for result in results if not result.flaky_flag]
        count = len(included)
        if count == 0:
            return cls(
                eval_run_id=eval_run_id,
                instance_count=0,
                single_file_count=0,
                multi_file_count=0,
                top1_rate=0.0,
                top3_rate=0.0,
                topN_rate=0.0,
                fl_conditioned_repair_rate=0.0,
            )
        conditioned = [
            result
            for result in included
            if result.fl_top1_correct or result.fl_top3_correct
        ]
        return cls(
            eval_run_id=eval_run_id,
            instance_count=count,
            single_file_count=sum(1 for result in included if _gold_count(result) <= 1),
            multi_file_count=sum(1 for result in included if _gold_count(result) > 1),
            top1_rate=sum(result.fl_top1_correct for result in included) / count,
            top3_rate=sum(result.fl_top3_correct for result in included) / count,
            topN_rate=sum(result.fl_topN_correct for result in included) / count,
            fl_conditioned_repair_rate=(
                sum(result.repair_correct for result in conditioned) / len(conditioned)
                if conditioned
                else 0.0
            ),
            per_instance_results=[
                {
                    "instance_id": result.instance_id,
                    "top1": result.fl_top1_correct,
                    "top3": result.fl_top3_correct,
                    "topN": result.fl_topN_correct,
                }
                for result in included
            ],
        )


def _gold_count(result: EvalInstanceResult) -> int:
    if result.notes and result.notes.startswith("gold_count="):
        return int(result.notes.split("=", 1)[1].split(";", 1)[0])
    return 1


def score_instance(
    *,
    ranked_files: list[str],
    gold_suspects: list[SuspectRecord],
    budget_n: int,
) -> tuple[bool, bool, bool]:
    gold_files = [suspect.file_path for suspect in gold_suspects]
    if not gold_files:
        return False, False, False
    gold_count = len(set(gold_files))
    top1_budget = max(1, gold_count)
    top3_budget = max(3, 3 * gold_count)
    gold_set = set(gold_files)
    return (
        gold_set.issubset(set(ranked_files[:top1_budget])),
        gold_set.issubset(set(ranked_files[:top3_budget])),
        gold_set.issubset(set(ranked_files[: max(budget_n, gold_count)])),
    )
