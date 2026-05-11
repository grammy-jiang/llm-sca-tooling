"""Replay helpers for stored eval artefacts."""

from __future__ import annotations

from llm_sca_tooling.evaluation.fl_metrics import FLMetricsAggregator
from llm_sca_tooling.evaluation.models import EvalInstanceResult

__all__ = ["replay_fl_metrics"]


def replay_fl_metrics(
    eval_run_id: str, instances: list[EvalInstanceResult]
) -> FLMetricsAggregator:
    return FLMetricsAggregator.from_instances(eval_run_id, instances)
