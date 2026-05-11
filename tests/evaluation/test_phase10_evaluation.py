from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from llm_sca_tooling.evaluation.ai_readiness import generate_ai_readiness_report
from llm_sca_tooling.evaluation.artefact_writer import EvalStore
from llm_sca_tooling.evaluation.benchmark_adapter import GoldPatchRecord, SuspectRecord
from llm_sca_tooling.evaluation.contamination import unknown_canary
from llm_sca_tooling.evaluation.fl_metrics import FLMetricsAggregator, score_instance
from llm_sca_tooling.evaluation.flaky_detector import detect_flakiness
from llm_sca_tooling.evaluation.harness_condition import (
    HarnessConditionSheet,
    diff_sheets,
)
from llm_sca_tooling.evaluation.maintainability_oracle import evaluate_diff
from llm_sca_tooling.evaluation.models import EvalInstanceResult, EvalRun, EvalStatus
from llm_sca_tooling.evaluation.operational_metrics import compute_operational_metrics
from llm_sca_tooling.evaluation.rds_features import compute_rds_features
from llm_sca_tooling.evaluation.regression_adapter import compare_snapshots
from llm_sca_tooling.evaluation.replay import replay_fl_metrics
from llm_sca_tooling.evaluation.smoke_adapter import LocalSmokeAdapter
from llm_sca_tooling.evaluation.t1_runner import run_t1_null
from llm_sca_tooling.evaluation.t2_runner import run_t2_skeleton, run_tier_stub
from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.context import McpServerContext
from llm_sca_tooling.mcp_server.prompts import PromptRegistry, register_default_prompts
from llm_sca_tooling.mcp_server.resources import register_core_resources
from llm_sca_tooling.mcp_server.sampling import SamplingCapability
from llm_sca_tooling.mcp_server.tasks import TaskManager
from llm_sca_tooling.mcp_server.tool_registry import ToolRegistry
from llm_sca_tooling.mcp_server.tools import register_core_tools

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "smoke"


def make_eval_run() -> EvalRun:
    run_id = "eval:test"
    return EvalRun(
        eval_run_id=run_id,
        suite_id="smoke",
        suite_version="v1",
        suite_median_age_days=10,
        target_workflow="fault-localisation",
        target_tool="get_relevant_files",
        model_backend="null",
        toolset_hash="hash",
        policy_id="policy",
        permission_profile="read/search",
        harness_condition_id=f"hcs:{run_id}",
        status=EvalStatus.completed,
        instance_count=1,
        contamination_canary_result=unknown_canary(
            eval_run_id=run_id, model_id="null", probe_instance_id="probe"
        ),
        artefact_manifest_ref="memory://manifest",
    )


def test_eval_models_round_trip_and_validate() -> None:
    run = make_eval_run()
    assert EvalRun.model_validate_json(run.model_dump_json()) == run
    with pytest.raises(ValidationError):
        EvalRun.model_validate({"suite_id": "missing"})
    instance = EvalInstanceResult(
        instance_id="i1",
        eval_run_id=run.eval_run_id,
        suite_id="smoke",
        issue_ref="issue",
        gate_results=[{"name": "gate", "passed": True}],
    )
    assert instance.gate_results[0]["passed"] is True
    assert make_eval_run().eval_run_id == make_eval_run().eval_run_id


def test_harness_condition_render_and_diff() -> None:
    sheet = HarnessConditionSheet.create(run_id="eval:test", model_backend="null")
    assert "model=null" in sheet.render_compact()
    assert "permission_mode=read/search" in sheet.render_kv()
    changed = sheet.model_copy(update={"model_backend": "other"})
    assert diff_sheets(sheet, changed)["model_backend"] == ("null", "other")
    assert sheet.render_compact() == sheet.render_compact()
    with pytest.raises(ValidationError):
        HarnessConditionSheet.model_validate(
            {**sheet.model_dump(mode="json"), "manifest_hashes": {}}
        )


def test_smoke_adapter_loads_instances_and_freshness() -> None:
    adapter = LocalSmokeAdapter(FIXTURE_ROOT)
    instances = adapter.list_instances()
    tags = {tag for instance in instances for tag in instance.difficulty_tags}
    assert {
        "file-localisation",
        "multi-file",
        "ambiguity",
        "security",
        "maintainability",
    } <= tags
    assert adapter.load_gold_suspects("file_local")[0].file_path == "src/parser.py"
    assert adapter.freshness_check().median_age_days == 20


def test_rds_features_with_null_diagnostics() -> None:
    vector = compute_rds_features(
        instance_id="i",
        eval_run_id="eval",
        gold_patch=GoldPatchRecord(
            instance_id="i",
            diff="+++ b/src/x.py\n",
            changed_files=[],
        ),
    )
    assert vector.files_touched == 1
    assert vector.memorisation_distance == 0.5
    assert vector.memorisation_calibrated is False
    assert vector.model_validate_json(vector.model_dump_json()) == vector


def test_fl_metrics_single_and_multi_file() -> None:
    single = [SuspectRecord(file_path="a.py")]
    multi = [SuspectRecord(file_path="a.py"), SuspectRecord(file_path="b.py")]
    assert score_instance(ranked_files=["a.py"], gold_suspects=single, budget_n=1) == (
        True,
        True,
        True,
    )
    assert score_instance(
        ranked_files=["a.py", "b.py"], gold_suspects=multi, budget_n=2
    )[0]
    results = [
        EvalInstanceResult(
            instance_id="i1",
            eval_run_id="eval",
            suite_id="smoke",
            issue_ref="issue",
            fl_top1_correct=True,
            fl_top3_correct=True,
            fl_topN_correct=True,
            repair_correct=True,
        ),
        EvalInstanceResult(
            instance_id="i2",
            eval_run_id="eval",
            suite_id="smoke",
            issue_ref="issue",
            fl_top1_correct=False,
            fl_top3_correct=True,
            fl_topN_correct=True,
            repair_correct=False,
            notes="gold_count=2;",
        ),
    ]
    aggregate = FLMetricsAggregator.from_instances("eval", results)
    assert aggregate.top1_rate == 0.5
    assert aggregate.multi_file_count == 1
    assert replay_fl_metrics("eval", results).top3_rate == 1.0


def test_operational_metrics_detect_missing_events() -> None:
    result = EvalInstanceResult(
        instance_id="i", eval_run_id="eval", suite_id="s", issue_ref="issue"
    )
    partial = compute_operational_metrics(
        eval_run_id="eval", instance_results=[result], run_events=[]
    )
    complete = compute_operational_metrics(
        eval_run_id="eval",
        instance_results=[result],
        run_events=[
            {"instance_id": "i", "type": "tool_call"},
            {"instance_id": "i", "type": "gate_result"},
            {"instance_id": "i", "type": "budget_event"},
            {"instance_id": "i", "type": "final_verdict"},
        ],
    )
    assert partial.process_compliance_rate == 0.0
    assert complete.process_compliance_rate == 1.0


def test_contamination_and_flaky_records() -> None:
    assert (
        unknown_canary(
            eval_run_id="eval", model_id="m", probe_instance_id="p"
        ).canary_verdict
        == "unknown"
    )
    stable = detect_flakiness(
        instance_id="i", eval_run_id="eval", outcomes=[True, True, True]
    )
    flaky = detect_flakiness(
        instance_id="i", eval_run_id="eval", outcomes=[True, False, True]
    )
    known = detect_flakiness(
        instance_id="i", eval_run_id="eval", outcomes=[], known_flaky=True
    )
    assert stable.excluded_from_aggregate is False
    assert flaky.excluded_from_aggregate is True
    assert known.detection_method == "known_flaky_list"


def test_t1_runner_stores_eval_run(tmp_path) -> None:
    store = EvalStore(tmp_path / "eval.sqlite")
    run = run_t1_null(adapter=LocalSmokeAdapter(FIXTURE_ROOT), store=store)
    assert run.status == EvalStatus.completed
    assert run.instance_count == 5
    assert run.harness_condition_id.startswith("hcs:")
    stored = store.get_eval_run(run.eval_run_id)
    assert stored is not None
    assert stored.fl_metrics["instance_count"] == 5
    assert store.resource_payload(run.eval_run_id)["eval_run_id"] == run.eval_run_id
    assert store.resource_payload("latest")["eval_run_id"] == run.eval_run_id


def test_t2_and_external_stubs() -> None:
    verdict = run_t2_skeleton(current_eval_run_id="current", suite_median_age_days=31)
    assert verdict.verdict == "inconclusive"
    assert verdict.freshness_warning is not None
    assert run_tier_stub("t3").status == "implemented_in_phase_18"
    with pytest.raises(ValueError):
        run_tier_stub("t5")


def test_maintainability_oracle_and_readiness(tmp_path) -> None:
    diff = "+++ b/src/llm_sca_tooling/evaluation/a.py\n+++ b/src/b.py\n"
    result = evaluate_diff(oracle_run_id="o", diff_id="d", diff_text=diff)
    assert result.change_locality_score == 0.8
    assert result.overall_pass is True
    (tmp_path / "AGENTS.md").write_text("hc", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    for idx in range(6):
        (tmp_path / "docs" / f"d{idx}.md").write_text("doc", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "Makefile").write_text("verify:\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    report = generate_ai_readiness_report(
        repo_root=tmp_path, repo_id="repo", eval_run_id="eval", previous_total_score=10
    )
    assert report.total_score >= 20
    assert report.no_regression_check_pass is True


def test_manifest_regression_classifies_policy_change() -> None:
    result = compare_snapshots(
        run_id="run",
        eval_run_id="eval",
        scope="tools",
        baseline={"tool": {"permission": "read"}},
        current={"tool": {"permission": "execute"}},
    )
    assert result.overall_verdict == "policy-relevant"
    assert result.changed_items == ["tool"]
    added = compare_snapshots(
        run_id="run",
        eval_run_id="eval",
        scope="tools",
        baseline={},
        current={"new": {"permission": "read"}},
    )
    removed = compare_snapshots(
        run_id="run",
        eval_run_id="eval",
        scope="tools",
        baseline={"old": {"permission": "read"}},
        current={},
    )
    assert added.overall_verdict == "compatible"
    assert removed.overall_verdict == "breaking"


@pytest.mark.asyncio
async def test_eval_tools_resource_and_prompt(tmp_path) -> None:
    config = McpServerConfig(workspace_path=tmp_path, in_memory_workspace=True)
    context = await McpServerContext.create(config)
    try:
        tools = ToolRegistry()
        tasks = TaskManager(tmp_path, config, context.telemetry)
        handlers = register_core_tools(tools, context, tasks)
        run_result = await handlers.run_eval_suite(
            {
                "suite": "smoke",
                "fixture_root": str(FIXTURE_ROOT),
                "model_backend": "null",
            }
        )
        run = run_result.payload["eval_run"]
        assert run_result.notifications
        rds_result = await handlers.compute_rds_features({"instance_id": "i"})
        assert rds_result.payload["memorisation_calibrated"] is False
        stored_result = await handlers.record_eval_result({"eval_run": run})
        assert stored_result.payload["eval_run_id"] == run["eval_run_id"]
        queued = await handlers.run_eval_suite(
            {"suite": "smoke", "fixture_root": str(FIXTURE_ROOT), "task": True}
        )
        assert queued.status == "queued"
        for _ in range(20):
            task_id = queued.payload["task"]["task_id"]
            if tasks.get(task_id, include_expired=True).status == "completed":
                break
            await asyncio.sleep(0.01)
        assert tasks.result(task_id)["result_available"] is True
        resources = __import__(
            "llm_sca_tooling.mcp_server.resource_registry",
            fromlist=["ResourceRegistry"],
        ).ResourceRegistry()
        resource_handlers = register_core_resources(resources, context)
        payload = await resource_handlers.eval_run(
            f"code-intelligence://eval/{run['eval_run_id']}"
        )
        assert payload.payload["eval_run_id"] == run["eval_run_id"]
        with pytest.raises(Exception):
            await resource_handlers.eval_run("code-intelligence://eval/missing")
        prompt_registry = PromptRegistry(SamplingCapability(status="unsupported"))
        register_default_prompts(prompt_registry)
        prompt = prompt_registry.get("evaluate")
        assert "FL-conditioned repair rate" in prompt["instructions"]
        assert "contamination" in prompt["instructions"]
    finally:
        await context.close()


@pytest.mark.asyncio
async def test_run_eval_suite_rejects_unknown_suite(tmp_path) -> None:
    config = McpServerConfig(workspace_path=tmp_path, in_memory_workspace=True)
    context = await McpServerContext.create(config)
    try:
        handlers = register_core_tools(
            ToolRegistry(), context, TaskManager(tmp_path, config, context.telemetry)
        )
        with pytest.raises(Exception):
            await handlers.run_eval_suite({"suite": "t2"})
        result = await handlers.run_eval_suite({"suite": "t4"})
        assert result.payload["eval_run"]["suite_id"] == "t4-implementation-spec"
    finally:
        await context.close()
