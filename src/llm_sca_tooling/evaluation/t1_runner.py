"""T1 local smoke evaluation runner."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from llm_sca_tooling.evaluation.ai_readiness import generate_ai_readiness_report
from llm_sca_tooling.evaluation.artefact_writer import EvaluationArtifactWriter
from llm_sca_tooling.evaluation.benchmark_adapter import BenchmarkAdapter
from llm_sca_tooling.evaluation.fl_metrics import (
    aggregate_fl_metrics,
    compute_instance_fl_metrics,
)
from llm_sca_tooling.evaluation.flaky_detector import detect_flaky_test
from llm_sca_tooling.evaluation.harness_condition import (
    HarnessConditionSheet,
    default_harness_condition_sheet,
)
from llm_sca_tooling.evaluation.models import (
    EvalInstanceResult,
    EvalRun,
    EvalStatus,
    GateResult,
    new_eval_run_id,
    utc_now_ts,
)
from llm_sca_tooling.evaluation.operational_metrics import (
    compute_operational_quality_metrics,
)
from llm_sca_tooling.evaluation.rds_features import (
    compute_rds_features,
    summarise_rds_features,
)
from llm_sca_tooling.evaluation.regression_adapter import compare_manifest_snapshots
from llm_sca_tooling.evaluation.store import EvalRunStore


class T1SmokeRunner:
    def __init__(self, adapter: BenchmarkAdapter, workspace: Any | None = None) -> None:
        self.adapter = adapter
        self.workspace = workspace

    def run(
        self,
        *,
        instance_ids: list[str] | None = None,
        model_backend: str = "null",
        policy_id: str = "policy:phase10-null",
        permission_profile: str = "scoped-execute",
        null_mode: bool = True,
        harness_condition: HarnessConditionSheet | None = None,
    ) -> EvalRun:
        eval_run_id = new_eval_run_id()
        descriptors = self.adapter.list_instances()
        if instance_ids is not None:
            wanted = set(instance_ids)
            descriptors = [
                descriptor
                for descriptor in descriptors
                if descriptor.instance_id in wanted
            ]
        start_ts = utc_now_ts()
        instance_results: list[EvalInstanceResult] = []
        fl_results = []
        flaky_records = []
        conn = getattr(self.workspace, "conn", None)
        for descriptor in descriptors:
            start = perf_counter()
            issue = self.adapter.load_issue(descriptor.instance_id)
            gold_patch = self.adapter.load_gold_patch(descriptor.instance_id)
            suspects = self.adapter.load_gold_suspects(descriptor.instance_id)
            ranked_files = [suspect.file_path for suspect in suspects]
            if not ranked_files:
                ranked_files = list(gold_patch.touched_files)
            rds = compute_rds_features(
                eval_run_id=eval_run_id,
                descriptor=descriptor,
                issue=issue,
                gold_patch=gold_patch,
                conn=conn,
            )
            fl_metric = compute_instance_fl_metrics(
                eval_run_id=eval_run_id,
                instance_id=descriptor.instance_id,
                gold_files=gold_patch.touched_files,
                ranked_files=ranked_files,
                budget_n=max(len(ranked_files), len(gold_patch.touched_files), 1),
                repair_correct=False,
                language=issue.language,
            )
            flaky = detect_flaky_test(
                eval_run_id=eval_run_id,
                instance_id=descriptor.instance_id,
                outcomes=[True],
                method="deterministic_only",
            )
            flaky_records.append(flaky)
            fl_results.append(fl_metric)
            wall_ms = int((perf_counter() - start) * 1000)
            gate_results = [
                GateResult(
                    gate_id="fl_top3",
                    status="passed" if fl_metric.fl_top3_correct else "failed",
                    passed=fl_metric.fl_top3_correct,
                ),
                GateResult(gate_id="final_verdict", status="passed", passed=True),
            ]
            instance_results.append(
                EvalInstanceResult(
                    instance_id=descriptor.instance_id,
                    eval_run_id=eval_run_id,
                    suite_id=self.adapter.suite_id,
                    issue_ref=descriptor.issue_ref,
                    gold_patch_ref=descriptor.gold_patch_ref,
                    candidate_patch_ref=None,
                    fl_result_ref="null-mode:fixture-suspects" if null_mode else None,
                    fl_top1_correct=fl_metric.fl_top1_correct,
                    fl_top3_correct=fl_metric.fl_top3_correct,
                    fl_topN_correct=fl_metric.fl_topN_correct,
                    fl_conditioned_repair_correct=(
                        fl_metric.fl_conditioned_repair_correct
                    ),
                    repair_correct=fl_metric.repair_correct,
                    gate_results=gate_results,
                    rds_features=rds,
                    contamination_flag=False,
                    flaky_flag=flaky.flaky_flag,
                    wall_ms=wall_ms,
                    token_count=len(issue.body.split()),
                    budget_events=[
                        {"type": "tool_call", "tool": "run_eval_suite"},
                        {"type": "budget_event", "budget": "null-mode"},
                        {"type": "final_verdict", "status": "recorded"},
                    ],
                    notes=["phase10 null-mode run"],
                )
            )
        excluded = [
            record.instance_id
            for record in flaky_records
            if record.excluded_from_aggregate
        ]
        aggregate = aggregate_fl_metrics(
            eval_run_id, fl_results, flaky_instance_ids=excluded
        )
        operational = compute_operational_quality_metrics(eval_run_id, instance_results)
        freshness = self.adapter.freshness_check()
        canary = self.adapter.contamination_canary(eval_run_id, model_backend)
        hcs = harness_condition or default_harness_condition_sheet(
            run_id=eval_run_id,
            model_backend=model_backend,
            tool_set=[
                "run_eval_suite",
                "compute_rds_features",
                "record_eval_result",
            ],
            permission_mode=permission_profile,
        )
        manifest = compare_manifest_snapshots(
            run_id=f"run:{eval_run_id.removeprefix('eval:')}",
            eval_run_id=eval_run_id,
            scope="phase10-null",
            baseline={},
            current={},
        )
        repo_root = getattr(self.workspace, "storage_root", None)
        readiness = None
        if repo_root is not None:
            readiness = generate_ai_readiness_report(
                repo_root.parent,
                repo_id="workspace",
                eval_run_id=eval_run_id,
                harness_stage=hcs.harness_stage,
            )
        run = EvalRun(
            eval_run_id=eval_run_id,
            suite_id=self.adapter.suite_id,
            suite_version=self.adapter.suite_version,
            suite_median_age_days=freshness.median_age_days,
            target_workflow="fault_localisation",
            target_tool="get_relevant_files:null-mode",
            model_backend=model_backend,
            toolset_hash=hcs.tool_set_hash,
            policy_id=policy_id,
            permission_profile=permission_profile,
            harness_condition_id=hcs.hcs_id,
            start_ts=start_ts,
            end_ts=utc_now_ts(),
            status=EvalStatus.COMPLETED,
            instance_count=len(instance_results),
            contamination_canary_result=canary,
            freshness_check_ts=freshness.freshness_check_ts,
            run_record_id=None,
            notes=[
                "T1 smoke null-mode baseline",
                "No external benchmark, network, or LLM calls were used.",
            ],
            instance_results=instance_results,
            aggregate_metrics=aggregate,
            rds_summary=summarise_rds_features(
                [result.rds_features for result in instance_results]
            ),
            operational_metrics=operational,
            freshness_record=freshness,
            harness_condition=hcs.model_dump(mode="json"),
            manifest_regression=manifest,
            ai_readiness_report=readiness,
        )
        if self.workspace is not None:
            run = EvaluationArtifactWriter(self.workspace).write_eval_run_bundle(run)
            EvalRunStore(self.workspace.conn).record_eval_run(run)
        return run
