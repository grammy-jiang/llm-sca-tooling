"""Tests for select_patch."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import (
    CandidatePatch,
    GateRunnerResult,
)
from llm_sca_tooling.workflows.bug_resolve.patch_selection import select_patch


def _candidate(idx: int) -> CandidatePatch:
    return CandidatePatch(run_id="r1", candidate_index=idx)


def _gate(
    idx: int, *, passed: bool, reasons: list[str] | None = None
) -> GateRunnerResult:
    return GateRunnerResult(
        run_id="r1",
        candidate_index=idx,
        sarif_gate_pass=passed or None,
        overall_gate_pass=passed,
        block_reasons=list(reasons or []),
    )


def test_single_passing_candidate_selected() -> None:
    res = select_patch(
        run_id="r1",
        candidates=[_candidate(0)],
        gate_results=[_gate(0, passed=True)],
        risk_results=[{"calibrated_probability": 0.1}],
        agreement_score=0.7,
    )
    assert res.selected_candidate_index == 0


def test_no_passing_candidates_returns_none() -> None:
    res = select_patch(
        run_id="r1",
        candidates=[_candidate(0)],
        gate_results=[_gate(0, passed=False, reasons=["build_failed"])],
    )
    assert res.selected_candidate_index is None
    assert res.rejected_candidates == [0]
    assert "build_failed" in res.rejection_reasons[0]


def test_multi_candidate_lower_risk_preferred() -> None:
    res = select_patch(
        run_id="r1",
        candidates=[_candidate(0), _candidate(1)],
        gate_results=[_gate(0, passed=True), _gate(1, passed=True)],
        risk_results=[
            {"calibrated_probability": 0.9},
            {"calibrated_probability": 0.1},
        ],
        agreement_score=0.5,
    )
    assert res.selected_candidate_index == 1


def test_rejection_reasons_populated() -> None:
    res = select_patch(
        run_id="r1",
        candidates=[_candidate(0), _candidate(1)],
        gate_results=[
            _gate(0, passed=False, reasons=["sarif"]),
            _gate(1, passed=True),
        ],
    )
    assert res.selected_candidate_index == 1
    assert 0 in res.rejected_candidates
