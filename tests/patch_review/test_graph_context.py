"""Tests for graph_context."""

from __future__ import annotations

from llm_sca_tooling.patch_review.diff_parser import parse_unified_diff
from llm_sca_tooling.patch_review.graph_context import extract_graph_context
from llm_sca_tooling.patch_review.models import ConfidenceLevel
from llm_sca_tooling.patch_review.symbol_detector import detect_changed_symbols


def _diff(text: str):
    return parse_unified_diff(text)


def test_two_hop_callers_callees_and_tests() -> None:
    diff = _diff(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1,2 +1,2 @@\n-def f():\n+def f():\n+    return 1\n"
    )
    symbols = detect_changed_symbols(diff, graph_node_ids={"x.py:f": "n:f"})
    record = extract_graph_context(
        diff,
        symbols,
        callers={"n:f": ["n:c1"], "n:c1": ["n:c2"]},
        callees={"n:f": ["n:e1"], "n:e1": ["n:e2"]},
        tests_for_symbol={"n:f": ["t1"]},
        coverage_available=True,
        snapshot_id="snap",
    )
    assert "n:c1" in record.two_hop_callers
    assert "n:c2" in record.two_hop_callers
    assert "n:e1" in record.two_hop_callees
    assert "n:e2" in record.two_hop_callees
    assert record.tests_exercising_changed_nodes == ["t1"]
    assert record.test_count == 1
    assert record.confidence == ConfidenceLevel.ANALYSER


def test_no_graph_data_yields_unknown_confidence() -> None:
    diff = _diff(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
    )
    symbols = detect_changed_symbols(diff)
    record = extract_graph_context(diff, symbols)
    assert record.confidence == ConfidenceLevel.UNKNOWN
    assert any(d["code"] == "no_test_evidence" for d in record.diagnostics)


def test_snapshot_lag_emits_diagnostic() -> None:
    diff = _diff(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
    )
    symbols = detect_changed_symbols(diff)
    record = extract_graph_context(
        diff, symbols, callers={"a": []}, snapshot_lag_commits=3
    )
    assert any(d.get("code") == "snapshot_stale" for d in record.diagnostics)


def test_interface_boundary_node_recorded() -> None:
    diff = _diff(
        "diff --git a/api/routes/x.py b/api/routes/x.py\n"
        "--- a/api/routes/x.py\n+++ b/api/routes/x.py\n"
        "@@ -1 +1 @@\n-a\n+b\n"
    )
    symbols = detect_changed_symbols(diff)
    record = extract_graph_context(diff, symbols, callers={"x": []})
    assert record.interface_boundary_nodes
