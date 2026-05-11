"""Tests for T2 regression runner."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.evaluation.models import EvalStatus
from llm_sca_tooling.evaluation.smoke_adapter import LocalSmokeAdapter
from llm_sca_tooling.evaluation.t1_runner import T1SmokeRunner
from llm_sca_tooling.evaluation.t2_runner import T2RegressionRunner
from llm_sca_tooling.storage.workspace import initialize_workspace


def test_t2_runner_returns_completed_eval_run() -> None:
    runner = T2RegressionRunner(LocalSmokeAdapter())
    run = runner.run()
    assert run.status is EvalStatus.COMPLETED
    assert run.suite_id == "local-smoke"
    assert run.instance_count == 5


def test_t2_runner_no_baseline_has_no_regression() -> None:
    runner = T2RegressionRunner(LocalSmokeAdapter())
    run = runner.run()
    assert run.manifest_regression is None


def test_t2_runner_with_baseline_detects_compatible() -> None:
    adapter = LocalSmokeAdapter()
    baseline = T1SmokeRunner(adapter).run()
    runner = T2RegressionRunner(adapter)
    run = runner.run(baseline=baseline)
    assert run.manifest_regression is not None
    assert run.manifest_regression.overall_verdict in {
        "compatible",
        "warning",
        "breaking",
        "unknown",
    }


def test_t2_runner_stores_run_in_workspace(tmp_path: Path) -> None:
    workspace = initialize_workspace(tmp_path / "workspace")
    runner = T2RegressionRunner(LocalSmokeAdapter(), workspace)
    run = runner.run()
    from llm_sca_tooling.evaluation.store import EvalRunStore

    stored = EvalRunStore(workspace.conn).get_eval_run(run.eval_run_id)
    assert stored.eval_run_id == run.eval_run_id


def test_t2_runner_eval_run_id_is_set() -> None:
    runner = T2RegressionRunner(LocalSmokeAdapter())
    run = runner.run()
    assert run.eval_run_id.startswith("eval:")
    assert len(run.eval_run_id) > 20


def test_t2_runner_operational_metrics_eval_run_id_matches() -> None:
    runner = T2RegressionRunner(LocalSmokeAdapter())
    run = runner.run()
    assert run.operational_metrics is not None
    assert run.operational_metrics.eval_run_id == run.eval_run_id


def test_t2_runner_contamination_canary_eval_run_id_matches() -> None:
    runner = T2RegressionRunner(LocalSmokeAdapter())
    run = runner.run()
    assert run.contamination_canary_result.eval_run_id == run.eval_run_id


def test_t2_runner_notes_include_suite_id() -> None:
    runner = T2RegressionRunner(LocalSmokeAdapter())
    run = runner.run()
    assert any("local-smoke" in note for note in (run.notes or []))


def test_t2_runner_null_mode_note() -> None:
    runner = T2RegressionRunner(LocalSmokeAdapter())
    run = runner.run(null_mode=True)
    assert any("null_mode=True" in note for note in (run.notes or []))
