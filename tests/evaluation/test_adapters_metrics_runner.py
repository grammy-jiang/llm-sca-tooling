from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.evaluation.ai_readiness import generate_ai_readiness_report
from llm_sca_tooling.evaluation.fl_metrics import (
    aggregate_fl_metrics,
    compute_instance_fl_metrics,
)
from llm_sca_tooling.evaluation.flaky_detector import detect_flaky_test
from llm_sca_tooling.evaluation.maintainability_oracle import (
    evaluate_maintainability,
)
from llm_sca_tooling.evaluation.operational_metrics import (
    compute_operational_quality_metrics,
)
from llm_sca_tooling.evaluation.rds_features import compute_rds_features
from llm_sca_tooling.evaluation.regression_adapter import compare_manifest_snapshots
from llm_sca_tooling.evaluation.smoke_adapter import LocalSmokeAdapter
from llm_sca_tooling.evaluation.t1_runner import T1SmokeRunner


def test_local_smoke_adapter_loads_required_fixture_types() -> None:
    adapter = LocalSmokeAdapter()
    descriptors = adapter.list_instances()
    assert len(descriptors) == 5
    tags = {tag for descriptor in descriptors for tag in descriptor.difficulty_tags}
    assert {"file-localisation", "multi-file", "ambiguity", "security"}.issubset(tags)
    assert adapter.freshness_check().median_age_days is not None
    assert adapter.load_gold_suspects("file_localisation")


def test_rds_features_use_null_estimates_and_diagnostics() -> None:
    adapter = LocalSmokeAdapter()
    descriptor = adapter.list_instances()[0]
    vector = compute_rds_features(
        eval_run_id="eval:test",
        descriptor=descriptor,
        issue=adapter.load_issue(descriptor.instance_id),
        gold_patch=adapter.load_gold_patch(descriptor.instance_id),
    )
    assert vector.files_touched >= 1
    assert vector.memorisation_distance == 0.5
    assert not vector.memorisation_calibrated
    assert vector.chain_depth is None
    assert "chain_depth" in vector.diagnostics


def test_fl_metrics_handle_multi_file_windows_and_flaky_exclusion() -> None:
    first = compute_instance_fl_metrics(
        eval_run_id="eval:test",
        instance_id="one",
        gold_files=["a.py"],
        ranked_files=["a.py"],
        repair_correct=True,
    )
    multi = compute_instance_fl_metrics(
        eval_run_id="eval:test",
        instance_id="two",
        gold_files=["a.py", "b.py"],
        ranked_files=["a.py", "x.py", "b.py"],
        repair_correct=False,
    )
    assert first.fl_top1_correct
    assert not multi.fl_top1_correct
    assert multi.fl_top3_correct
    aggregate = aggregate_fl_metrics(
        "eval:test", [first, multi], flaky_instance_ids=["two"]
    )
    assert aggregate.instance_count == 1
    assert aggregate.top1_rate == 1.0


def test_t1_null_runner_completes_all_fixtures_and_operational_metrics() -> None:
    run = T1SmokeRunner(LocalSmokeAdapter()).run()
    assert run.status == "completed"
    assert run.instance_count == 5
    assert run.aggregate_metrics is not None
    assert run.aggregate_metrics.top3_rate == 1.0
    assert run.rds_summary is not None
    assert run.rds_summary["instance_count"] == 5
    assert run.operational_metrics is not None
    assert run.operational_metrics.process_compliance_rate == 1.0
    assert run.harness_condition is not None


def test_operational_metrics_detect_missing_gate_event() -> None:
    run = T1SmokeRunner(LocalSmokeAdapter()).run(instance_ids=["file_localisation"])
    instance = run.instance_results[0].model_copy(update={"gate_results": []})
    metrics = compute_operational_quality_metrics("eval:test", [instance])
    assert metrics.process_compliance_rate == 0.0
    assert metrics.trace_replay_success_rate == 0.0


def test_auxiliary_phase10_adapters() -> None:
    flaky = detect_flaky_test(
        eval_run_id="eval:test",
        instance_id="flaky",
        outcomes=[True, False, True, False],
    )
    assert flaky.flaky_flag
    oracle = evaluate_maintainability(
        "diff --git a/src/pkg/a.py b/src/pkg/a.py\n+++ b/src/pkg/a.py\n+value = 1\n"
    )
    assert oracle.overall_pass
    regression = compare_manifest_snapshots(
        run_id="run:test",
        eval_run_id="eval:test",
        scope="tools",
        baseline={"tool.permission": "read"},
        current={"tool.permission": "search"},
    )
    assert regression.overall_verdict == "policy-relevant"


def test_ai_readiness_report_scores_axes(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("HC1 HC2 HC3 HC4 HC5 HC6", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    report = generate_ai_readiness_report(
        tmp_path, repo_id="repo:test", eval_run_id="eval:test"
    )
    assert report.total_score > 0
    assert "agent_config" in report.axis_findings
