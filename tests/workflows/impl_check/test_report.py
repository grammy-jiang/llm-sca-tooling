from __future__ import annotations

import asyncio
from pathlib import Path

from llm_sca_tooling.workflows.impl_check.report import run_implementation_check


def _run(spec: str, **kwargs):
    return asyncio.run(run_implementation_check(spec, **kwargs))


def test_null_mode_returns_report_and_matrix() -> None:
    report, matrix = _run("# T\nThe `foo` function must work.\n")
    assert report.report_id.startswith("impl-check-report:")
    assert report.run_id
    assert matrix.clause_count >= 1


def test_all_clauses_unknown_overall_unknown() -> None:
    report, _ = _run("The system must work.\n")
    assert report.overall_verdict.value == "unknown"
    assert report.recommendation.value == "unknown"
    assert "insufficient_evidence" in report.uncertainty


def test_empty_spec_unknown() -> None:
    report, matrix = _run("")
    assert matrix.clause_count == 0
    assert report.overall_verdict.value == "unknown"


def test_harness_condition_id_in_report() -> None:
    report, _ = _run("must work.\n", harness_condition_id="hcs:abc")
    assert report.harness_condition_id == "hcs:abc"


def test_report_required_fields() -> None:
    report, _ = _run("must work.\n")
    assert report.doc_id
    assert report.spec_document_ref
    assert report.clause_verdict_matrix_ref
    assert report.created_ts


def test_grounded_clauses_satisfied_path() -> None:
    spec = "The `mylogin` function must validate inputs.\n"
    report, matrix = _run(spec, available_symbol_ids=["pkg.mod.mylogin"])
    assert matrix.satisfied_count >= 1
    assert report.overall_verdict.value in {"compliant", "partially_compliant"}


def test_violated_clause_via_missing_gate() -> None:
    spec = "HC1 hard constraint must be enforced.\n"
    report, matrix = _run(
        spec,
        required_gate_events=["secrets-scan"],
        gate_events_present={"secrets-scan": False},
    )
    assert matrix.violated_count >= 1
    assert report.overall_verdict.value == "non_compliant"
    assert report.recommendation.value == "block"


def test_loads_fixture_spec() -> None:
    p = Path(__file__).parent / "fixtures" / "specs" / "simple_feature_spec.md"
    text = p.read_text(encoding="utf-8")
    report, matrix = _run(text)
    assert matrix.clause_count >= 3
    assert report.doc_id


def test_explicit_run_id_used() -> None:
    report, _ = _run("must work.\n", run_id="custom:1")
    assert report.run_id == "custom:1"
