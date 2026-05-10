"""Tests for blast-radius stub."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.blast_radius_stub import (
    build_blast_radius_stub,
)


def test_always_partial() -> None:
    b = build_blast_radius_stub(
        run_id="r1",
        candidate_index=0,
        changed_symbol_ids=["s1"],
    )
    assert b.is_partial is True


def test_local_impact_count() -> None:
    b = build_blast_radius_stub(
        run_id="r1",
        candidate_index=0,
        changed_symbol_ids=["s1"],
        direct_callers=["c1", "c2"],
        downstream_tests=["t1"],
        interface_boundaries=["if1"],
        cross_language_candidates=[],
    )
    assert b.local_impact_count == 4


def test_empty_inputs() -> None:
    b = build_blast_radius_stub(run_id="r1", candidate_index=0, changed_symbol_ids=[])
    assert b.local_impact_count == 0
    assert b.changed_symbol_ids == []
