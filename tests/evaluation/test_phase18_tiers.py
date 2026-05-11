from __future__ import annotations

from llm_sca_tooling.evaluation.artefact_writer import EvalStore
from llm_sca_tooling.evaluation.t2_runner import run_tier_stub
from llm_sca_tooling.evaluation.t3_runner import run_t3_null
from llm_sca_tooling.evaluation.t4_runner import (
    build_t4_fixture_matrices,
    run_t4_null,
)


def test_t3_runner_stores_cross_language_eval_run(tmp_path) -> None:
    store = EvalStore(tmp_path / "eval.sqlite")
    run = run_t3_null(store=store)
    assert run.status == "completed"
    assert run.instance_count == 5
    assert run.fl_metrics["generated_file_impact_count"] == 1
    assert run.fl_metrics["blast_radius_recall"] == 1.0
    stored = store.get_eval_run(run.eval_run_id)
    assert stored is not None
    assert stored.suite_id == "t3-cross-language"


def test_t4_runner_stores_impl_spec_eval_run(tmp_path) -> None:
    store = EvalStore(tmp_path / "eval.sqlite")
    run = run_t4_null(store=store)
    assert run.status == "completed"
    assert run.instance_count == 5
    assert run.fl_metrics["unknown_clause_rate"] < 0.30
    matrices = build_t4_fixture_matrices(run.eval_run_id)
    assert any(matrix.violated_count for matrix in matrices)
    assert any(matrix.unknown_count for matrix in matrices)
    stored = store.get_eval_run(run.eval_run_id)
    assert stored is not None
    assert stored.suite_id == "t4-implementation-spec"


def test_tier_status_reports_phase18_implementation() -> None:
    assert run_tier_stub("t3").status == "implemented_in_phase_18"
    assert run_tier_stub("t4").verdict == "available"
