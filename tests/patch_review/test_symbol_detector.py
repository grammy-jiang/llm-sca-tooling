"""Tests for symbol_detector."""

from __future__ import annotations

from llm_sca_tooling.patch_review.diff_parser import parse_unified_diff
from llm_sca_tooling.patch_review.models import ChangeKind, ConfidenceLevel
from llm_sca_tooling.patch_review.symbol_detector import detect_changed_symbols


def test_detect_python_function(safe_diff: str) -> None:
    diff = parse_unified_diff(safe_diff)
    records = detect_changed_symbols(diff)
    assert records
    rec = records[0]
    assert rec.file_path == "src/util.py"
    assert rec.symbol_type in {"function", "module"}
    assert rec.change_kind in set(ChangeKind)
    assert rec.confidence in {
        ConfidenceLevel.HEURISTIC,
        ConfidenceLevel.UNKNOWN,
        ConfidenceLevel.ANALYSER,
    }


def test_detect_added_only_classified_added() -> None:
    diff = parse_unified_diff(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1,0 +1,2 @@\n+def new_fn():\n+    return 1\n"
    )
    records = detect_changed_symbols(diff)
    assert any(r.change_kind == ChangeKind.ADDED for r in records)


def test_detect_removed_only_classified_removed() -> None:
    diff = parse_unified_diff(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1,2 +1,0 @@\n-def gone():\n-    return 1\n"
    )
    records = detect_changed_symbols(diff)
    assert any(r.change_kind == ChangeKind.REMOVED for r in records)


def test_detect_signature_change_and_graph_lookup() -> None:
    diff = parse_unified_diff(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1,2 +1,2 @@\n-def foo(a):\n+def foo(a, b):\n"
    )
    records = detect_changed_symbols(diff, graph_node_ids={"x.py:foo": "node:foo"})
    assert records[0].change_kind == ChangeKind.MODIFIED_SIGNATURE
    assert records[0].graph_node_id == "node:foo"
    assert records[0].confidence == ConfidenceLevel.ANALYSER


def test_stale_index_marks_unknown() -> None:
    diff = parse_unified_diff(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1 +1 @@\n-line1\n+line2\n"
    )
    records = detect_changed_symbols(diff, stale_index=True)
    assert all(r.confidence == ConfidenceLevel.UNKNOWN for r in records)


def test_generated_and_interface_hints() -> None:
    diff = parse_unified_diff(
        "diff --git a/api/routes/items_pb2.py b/api/routes/items_pb2.py\n"
        "--- a/api/routes/items_pb2.py\n+++ b/api/routes/items_pb2.py\n"
        "@@ -1 +1 @@\n-a\n+b\n"
    )
    records = detect_changed_symbols(diff, public_api_paths=["api/routes/items_pb2.py"])
    assert records[0].is_generated
    assert records[0].is_interface_boundary
    assert records[0].is_public_api


def test_js_function_detection() -> None:
    diff = parse_unified_diff(
        "diff --git a/x.ts b/x.ts\n--- a/x.ts\n+++ b/x.ts\n"
        "@@ -1 +1,2 @@\n+export function hello() {\n+  return 1;\n"
    )
    records = detect_changed_symbols(diff)
    assert records[0].symbol_path.endswith("hello")
