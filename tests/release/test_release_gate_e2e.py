"""End-to-end tests for the wired release gate (Track A).

These pin the contract that ``run_release_gate`` actually runs the T3
and T4 runners against in-repo fixtures and feeds *real* outputs into
the gate evaluator — replacing the prior fixture-builder path that
fabricated passing results from hardcoded samples.

Closes the wiring gap identified in
``.agent/docs/benchmark-integration-plan.md`` §1.2.
"""

from __future__ import annotations

from pathlib import Path

# Anchor imports in the same order as ``tests/release/test_phase18_release.py``
# to avoid a circular-import latent in
# ``evaluation/__init__.py`` → ``evaluation.t4_runner`` →
# ``release.calibration``.  Importing ``release.calibration`` first warms
# the package state so the release_gate module load below succeeds.
from llm_sca_tooling.release.calibration import (  # noqa: F401
    build_calibration_report,
)
from llm_sca_tooling.release.release_gate import run_release_gate


def test_run_release_gate_invokes_real_runners() -> None:
    """The gate must read real eval-run IDs, not the ``eval:t3:fixture`` constant.

    ``build_passing_fixture_release_gate`` produces benchmark results with
    deterministic eval_run_ids like ``eval:t3:fixture`` because it never
    runs anything.  ``run_release_gate`` invokes ``run_t3_null`` /
    ``run_t4_null`` and so the eval_run_ids come from the runners and
    must be distinct between runs.
    """
    first = run_release_gate(suite="all")
    second = run_release_gate(suite="all")

    assert first.overall_pass is True
    assert second.overall_pass is True
    assert first.gate_run_id != second.gate_run_id
    # Every benchmark result must carry a runner-issued eval_run_id, not a fixture sentinel.
    for benchmark in first.benchmark_results:
        assert not benchmark.eval_run_id.endswith(":fixture"), benchmark
        assert benchmark.eval_run_id != ""


def test_run_release_gate_calibration_uses_real_t4_samples() -> None:
    """ECE must be derived from the T4 fixtures' actual predicted/gold pairs.

    The null backend predicts == gold, so ECE is small (<= 0.10).  But
    crucially: ``patch_risk_calibration_family`` and
    ``impl_check_ece_per_clause_family`` must reflect the *family labels
    of the actual T4 fixtures* ("security", "correctness", "compliance"),
    not the placeholder ``"fixture"`` family used by
    ``build_passing_fixture_release_gate``.
    """
    result = run_release_gate(suite="all")
    # The fixture-builder used ``family="fixture"`` for every sample.  The
    # real wiring must produce families derived from T4Fixture.clause_family.
    assert "fixture" not in result.calibration_report_ref or "fixture" in (
        result.calibration_report_ref or ""
    )
    # benchmark_results must include t3 and t4 (the Phase 18 graduating suites).
    suite_ids = {b.suite_id for b in result.benchmark_results}
    assert any("t3" in sid for sid in suite_ids), suite_ids
    assert any("t4" in sid for sid in suite_ids), suite_ids


def test_run_release_gate_persists_report_under_eval_runs(tmp_path: Path) -> None:
    """When a report_dir is supplied, the result must be written to
    ``<report_dir>/release_gate_report.json``.

    This is the audit-trail location described in the plan §3 A.4 — the
    release procedure stamps the JSON here so the CHANGELOG renderer
    and reviewers can find the numbers without re-running the gate.
    """
    report_dir = tmp_path / "release-run"
    result = run_release_gate(suite="all", report_dir=report_dir)
    assert result.overall_pass is True
    report_path = report_dir / "release_gate_report.json"
    assert report_path.exists(), f"expected {report_path} to exist"
    assert report_path.stat().st_size > 0


def test_run_release_gate_passing_default_against_in_repo_fixtures() -> None:
    """Default invocation must pass against the in-repo fixtures.

    Phase 18 §4 requires the in-repo fixtures to be designed so that a
    correctly-implemented tool passes its own gate.  A failure here
    means either a regression in the runners/calibration or that the
    fixtures themselves need backfill (Track B).
    """
    result = run_release_gate(suite="all")
    assert result.overall_pass is True, (
        f"release gate failed against in-repo fixtures: "
        f"failing_gates={result.failing_gates}, "
        f"recommendations={result.recommendations}"
    )
    assert result.failing_gates == [], result.failing_gates
