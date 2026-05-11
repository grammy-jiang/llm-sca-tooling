"""Phase 18 T3 cross-language benchmark runner."""

from __future__ import annotations

from collections import defaultdict

from pydantic import Field

from llm_sca_tooling.evaluation.artefact_writer import EvalStore
from llm_sca_tooling.evaluation.contamination import unknown_canary
from llm_sca_tooling.evaluation.harness_condition import HarnessConditionSheet
from llm_sca_tooling.evaluation.models import (
    EvalInstanceResult,
    EvalRun,
    EvalStatus,
    StrictEvalModel,
)
from llm_sca_tooling.evaluation.operational_metrics import compute_operational_metrics

__all__ = ["T3Fixture", "default_t3_fixtures", "run_t3_null"]


class T3Fixture(StrictEvalModel):
    instance_id: str
    benchmark_family: str
    languages: list[str]
    gold_impacted_nodes: list[str]
    predicted_impacted_nodes: list[str]
    interface_boundary_detected: bool
    generated_file_impact: bool = False
    resolved: bool = True
    notes: list[str] = Field(default_factory=list)


def default_t3_fixtures() -> list[T3Fixture]:
    return [
        T3Fixture(
            instance_id="swe-polybench-python-typescript-route",
            benchmark_family="swe-polybench",
            languages=["python", "typescript"],
            gold_impacted_nodes=["api.route", "client.fetch"],
            predicted_impacted_nodes=["api.route", "client.fetch"],
            interface_boundary_detected=True,
            notes=["http route contract"],
        ),
        T3Fixture(
            instance_id="swe-polybench-python-typescript-websocket",
            benchmark_family="swe-polybench",
            languages=["python", "typescript"],
            gold_impacted_nodes=["events.emit", "ui.subscribe"],
            predicted_impacted_nodes=["events.emit", "ui.subscribe"],
            interface_boundary_detected=True,
            notes=["websocket event contract"],
        ),
        T3Fixture(
            instance_id="swe-polybench-generated-client",
            benchmark_family="swe-polybench",
            languages=["python", "typescript"],
            gold_impacted_nodes=["openapi.schema", "generated.client"],
            predicted_impacted_nodes=["openapi.schema", "generated.client"],
            interface_boundary_detected=True,
            generated_file_impact=True,
            notes=["generated-file impact"],
        ),
        T3Fixture(
            instance_id="defects4c-cpp-header-abi",
            benchmark_family="defects4c",
            languages=["cpp"],
            gold_impacted_nodes=["lib.header", "lib.callsite"],
            predicted_impacted_nodes=["lib.header", "lib.callsite"],
            interface_boundary_detected=True,
            notes=["ABI signature"],
        ),
        T3Fixture(
            instance_id="defects4c-cpp-test-entry",
            benchmark_family="defects4c",
            languages=["cpp"],
            gold_impacted_nodes=["lib.parser", "tests.parser"],
            predicted_impacted_nodes=["lib.parser", "tests.parser"],
            interface_boundary_detected=True,
            notes=["CTest target"],
        ),
    ]


def run_t3_null(
    *,
    store: EvalStore | None = None,
    model_backend: str = "null",
    fixtures: list[T3Fixture] | None = None,
) -> EvalRun:
    fixtures = fixtures or default_t3_fixtures()
    eval_run = EvalRun(
        suite_id="t3-cross-language",
        suite_version="phase18.v1",
        suite_median_age_days=14.0,
        target_workflow="cross-language-evaluation",
        target_tool="run_eval_suite",
        model_backend=model_backend,
        toolset_hash="phase18-null",
        policy_id="phase18-null",
        permission_profile="read/search",
        harness_condition_id="pending",
        instance_count=len(fixtures),
        contamination_canary_result=unknown_canary(
            eval_run_id="pending", model_id=model_backend, probe_instance_id="unknown"
        ),
        artefact_manifest_ref="memory://phase18/t3",
    )
    hcs = HarnessConditionSheet.create(
        run_id=eval_run.eval_run_id, model_backend=model_backend
    )
    results = [_instance_result(fixture, eval_run.eval_run_id) for fixture in fixtures]
    eval_run.harness_condition_id = hcs.hcs_id
    eval_run.contamination_canary_result = unknown_canary(
        eval_run_id=eval_run.eval_run_id,
        model_id=model_backend,
        probe_instance_id=fixtures[0].instance_id if fixtures else "unknown",
    )
    eval_run.status = EvalStatus.completed
    eval_run.end_ts = hcs.created_ts
    eval_run.instance_results_ref = f"memory://eval/{eval_run.eval_run_id}/instances"
    eval_run.aggregate_metrics_ref = f"memory://eval/{eval_run.eval_run_id}/t3"
    eval_run.operational_metrics_ref = (
        f"memory://eval/{eval_run.eval_run_id}/operational"
    )
    eval_run.fl_metrics = _aggregate_t3_metrics(fixtures)
    eval_run.operational_metrics = compute_operational_metrics(
        eval_run_id=eval_run.eval_run_id,
        instance_results=results,
        run_events=_complete_events(results),
    )
    eval_run.manifest_regression = {"overall_verdict": "compatible", "findings": []}
    if store is not None:
        store.record_eval_run(eval_run)
    return eval_run


def _instance_result(fixture: T3Fixture, eval_run_id: str) -> EvalInstanceResult:
    recall = _recall(fixture.predicted_impacted_nodes, fixture.gold_impacted_nodes)
    return EvalInstanceResult(
        instance_id=fixture.instance_id,
        eval_run_id=eval_run_id,
        suite_id="t3-cross-language",
        issue_ref=f"memory://fixtures/t3/{fixture.instance_id}/issue",
        gold_patch_ref=f"memory://fixtures/t3/{fixture.instance_id}/gold_patch",
        fl_result_ref=f"memory://fixtures/t3/{fixture.instance_id}/fl",
        fl_top1_correct=recall > 0.0,
        fl_top3_correct=recall >= 0.5,
        fl_topN_correct=recall == 1.0,
        fl_conditioned_repair_correct=fixture.resolved and recall >= 0.5,
        repair_correct=fixture.resolved,
        gate_results=[
            {
                "name": "interface_boundary",
                "passed": fixture.interface_boundary_detected,
            },
            {"name": "blast_radius_recall", "passed": recall >= 0.5},
        ],
        contamination_flag="unknown",
        flaky_flag=False,
        budget_events=["none"],
        notes="; ".join(
            [
                fixture.benchmark_family,
                ",".join(fixture.languages),
                *fixture.notes,
            ]
        ),
    )


def _aggregate_t3_metrics(fixtures: list[T3Fixture]) -> dict[str, object]:
    by_language: dict[str, list[bool]] = defaultdict(list)
    recalls = []
    for fixture in fixtures:
        recall = _recall(fixture.predicted_impacted_nodes, fixture.gold_impacted_nodes)
        recalls.append(recall)
        for language in fixture.languages:
            by_language[language].append(fixture.resolved)
    return {
        "suite": "t3",
        "instance_count": len(fixtures),
        "resolve_rate_per_language": {
            language: sum(values) / len(values)
            for language, values in sorted(by_language.items())
        },
        "cross_language_fl_top1": sum(
            _recall(item.predicted_impacted_nodes, item.gold_impacted_nodes) > 0
            for item in fixtures
        )
        / len(fixtures),
        "cross_language_fl_top3": sum(recall >= 0.5 for recall in recalls)
        / len(recalls),
        "interface_boundary_detection_accuracy": sum(
            item.interface_boundary_detected for item in fixtures
        )
        / len(fixtures),
        "blast_radius_recall": sum(recalls) / len(recalls),
        "generated_file_impact_count": sum(
            item.generated_file_impact for item in fixtures
        ),
    }


def _recall(predicted: list[str], gold: list[str]) -> float:
    if not gold:
        return 1.0
    return len(set(predicted) & set(gold)) / len(set(gold))


def _complete_events(results: list[EvalInstanceResult]) -> list[dict[str, str]]:
    return [
        {"instance_id": result.instance_id, "type": event_type}
        for result in results
        for event_type in ("tool_call", "gate_result", "budget_event", "final_verdict")
    ]
