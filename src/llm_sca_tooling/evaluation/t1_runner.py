"""T1 smoke evaluation runner."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from llm_sca_tooling.evaluation.artefact_writer import EvalStore
from llm_sca_tooling.evaluation.benchmark_adapter import BenchmarkAdapter
from llm_sca_tooling.evaluation.contamination import unknown_canary
from llm_sca_tooling.evaluation.fl_metrics import FLMetricsAggregator, score_instance
from llm_sca_tooling.evaluation.flaky_detector import detect_flakiness
from llm_sca_tooling.evaluation.harness_condition import HarnessConditionSheet
from llm_sca_tooling.evaluation.models import EvalInstanceResult, EvalRun, EvalStatus
from llm_sca_tooling.evaluation.operational_metrics import compute_operational_metrics
from llm_sca_tooling.evaluation.rds_features import compute_rds_features
from llm_sca_tooling.evaluation.smoke_adapter import LocalSmokeAdapter

__all__ = ["REQUIRED_T1_TAGS", "run_t1_null"]

REQUIRED_T1_TAGS = {
    "file-localisation",
    "multi-file",
    "ambiguity",
    "security",
    "maintainability",
}


def run_t1_null(
    *,
    adapter: BenchmarkAdapter,
    store: EvalStore,
    model_backend: str = "null",
    instance_ids: list[str] | None = None,
) -> EvalRun:
    descriptors = adapter.list_instances()
    if instance_ids is not None:
        descriptors = [
            descriptor
            for descriptor in descriptors
            if descriptor.instance_id in instance_ids
        ]
    _validate_required_tags(descriptors)
    eval_run = EvalRun(
        suite_id=adapter.suite_id,
        suite_version=adapter.suite_version,
        suite_median_age_days=adapter.freshness_check().median_age_days,
        target_workflow="fault-localisation",
        target_tool="get_relevant_files",
        model_backend=model_backend,
        toolset_hash="phase10-null",
        policy_id="phase10-null",
        permission_profile="read/search",
        harness_condition_id="pending",
        instance_count=len(descriptors),
        contamination_canary_result=unknown_canary(
            eval_run_id="pending", model_id=model_backend, probe_instance_id="unknown"
        ),
        artefact_manifest_ref="memory://phase10/null",
    )
    hcs = HarnessConditionSheet.create(
        run_id=eval_run.eval_run_id, model_backend=model_backend
    )
    instance_results = [
        _run_instance(
            adapter=adapter,
            eval_run_id=eval_run.eval_run_id,
            instance_id=descriptor.instance_id,
        )
        for descriptor in descriptors
    ]
    fl_metrics = FLMetricsAggregator.from_instances(
        eval_run.eval_run_id, instance_results
    )
    operational = compute_operational_metrics(
        eval_run_id=eval_run.eval_run_id,
        instance_results=instance_results,
        run_events=_null_events(instance_results),
    )
    eval_run.harness_condition_id = hcs.hcs_id
    eval_run.contamination_canary_result = unknown_canary(
        eval_run_id=eval_run.eval_run_id,
        model_id=model_backend,
        probe_instance_id=descriptors[0].instance_id if descriptors else "unknown",
    )
    eval_run.status = EvalStatus.completed
    eval_run.end_ts = hcs.created_ts
    eval_run.instance_results_ref = f"memory://eval/{eval_run.eval_run_id}/instances"
    eval_run.aggregate_metrics_ref = f"memory://eval/{eval_run.eval_run_id}/fl"
    eval_run.rds_summary_ref = f"memory://eval/{eval_run.eval_run_id}/rds"
    eval_run.operational_metrics_ref = (
        f"memory://eval/{eval_run.eval_run_id}/operational"
    )
    eval_run.fl_metrics = fl_metrics.model_dump(mode="json")
    eval_run.operational_metrics = operational
    eval_run.manifest_regression = {
        "overall_verdict": "compatible",
        "findings": [],
    }
    store.record_eval_run(eval_run)
    return eval_run


def run_t1_fixture_suite(fixture_root: Path, store: EvalStore) -> EvalRun:
    return run_t1_null(adapter=LocalSmokeAdapter(fixture_root), store=store)


def _run_instance(
    *,
    adapter: BenchmarkAdapter,
    eval_run_id: str,
    instance_id: str,
) -> EvalInstanceResult:
    start = perf_counter()
    issue = adapter.load_issue(instance_id)
    patch = adapter.load_gold_patch(instance_id)
    suspects = adapter.load_gold_suspects(instance_id)
    rds = compute_rds_features(
        instance_id=instance_id, eval_run_id=eval_run_id, gold_patch=patch
    )
    ranked = [suspect.file_path for suspect in suspects]
    top1, top3, topn = score_instance(
        ranked_files=ranked,
        gold_suspects=suspects,
        budget_n=max(3, len(ranked)),
    )
    flaky = detect_flakiness(
        instance_id=instance_id,
        eval_run_id=eval_run_id,
        outcomes=[True, True, True],
    )
    return EvalInstanceResult(
        instance_id=instance_id,
        eval_run_id=eval_run_id,
        suite_id=adapter.suite_id,
        issue_ref=issue.instance_id,
        gold_patch_ref=patch.instance_id,
        fl_result_ref=f"memory://fl/{instance_id}",
        fl_top1_correct=top1,
        fl_top3_correct=top3,
        fl_topN_correct=topn,
        fl_conditioned_repair_correct=top1 or top3,
        repair_correct=top1 or top3,
        gate_results=[{"name": "null-mode", "passed": True}],
        rds_features=rds,
        contamination_flag="unknown",
        flaky_flag=flaky.excluded_from_aggregate,
        wall_ms=int((perf_counter() - start) * 1000),
        token_count=0,
        budget_events=["none"],
        notes=f"gold_count={len(suspects)}; {issue.language}",
    )


def _validate_required_tags(descriptors: list[Any]) -> None:
    observed = {tag for descriptor in descriptors for tag in descriptor.difficulty_tags}
    missing = REQUIRED_T1_TAGS - observed
    if missing:
        raise ValueError(f"T1 smoke suite missing required tags: {sorted(missing)}")


def _null_events(results: list[EvalInstanceResult]) -> list[dict[str, str]]:
    return [
        {"instance_id": result.instance_id, "type": event_type}
        for result in results
        for event_type in ("tool_call", "gate_result", "budget_event", "final_verdict")
    ]
