"""Tests for ast_diff."""

from __future__ import annotations

from llm_sca_tooling.patch_review.ast_diff import extract_ast_diff_features
from llm_sca_tooling.patch_review.diff_parser import parse_unified_diff
from llm_sca_tooling.patch_review.models import ConfidenceLevel, EditOperation


def _parse(text: str):
    return parse_unified_diff(text)


def test_signature_change_detected() -> None:
    diff = _parse(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1 +1 @@\n-def f(a) -> int:\n+def f(a, b) -> str:\n"
    )
    features = extract_ast_diff_features(diff)
    assert features.signature_changed
    assert features.return_type_changed
    assert features.parameter_count_delta == 1
    assert features.edit_operation == EditOperation.SIGNATURE_CHANGE


def test_added_function_only() -> None:
    diff = _parse(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1 +1,2 @@\n+def new_fn():\n+    return 1\n"
    )
    features = extract_ast_diff_features(diff)
    assert features.edit_operation == EditOperation.ADDED_FUNCTION


def test_removed_function_only() -> None:
    diff = _parse(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1,2 +1 @@\n-def gone():\n-    pass\n"
    )
    features = extract_ast_diff_features(diff)
    assert features.edit_operation == EditOperation.REMOVED_FUNCTION


def test_conditional_inserted_and_loop_inserted() -> None:
    cond = _parse(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1 +1,2 @@\n base\n+if x: pass\n"
    )
    assert (
        extract_ast_diff_features(cond).edit_operation
        == EditOperation.CONDITIONAL_INSERTED
    )

    loop = _parse(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1 +1,2 @@\n base\n+for i in r: pass\n"
    )
    assert extract_ast_diff_features(loop).edit_operation == EditOperation.LOOP_INSERTED


def test_conditional_removed_loop_removed_exception_handler() -> None:
    cond_rm = _parse(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1,2 +1 @@\n-if x: pass\n base\n"
    )
    assert (
        extract_ast_diff_features(cond_rm).edit_operation
        == EditOperation.CONDITIONAL_REMOVED
    )

    loop_rm = _parse(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1,2 +1 @@\n-for i in r: pass\n base\n"
    )
    assert (
        extract_ast_diff_features(loop_rm).edit_operation == EditOperation.LOOP_REMOVED
    )

    exc = _parse(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1 +1,2 @@\n base\n+try: pass\n"
    )
    assert (
        extract_ast_diff_features(exc).edit_operation
        == EditOperation.EXCEPTION_HANDLER_CHANGED
    )


def test_body_change_and_other_and_security() -> None:
    body = _parse(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    )
    assert extract_ast_diff_features(body).edit_operation == EditOperation.BODY_CHANGE

    sec = _parse(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1,2 +1 @@\n-@require_auth\n def f(): pass\n"
    )
    assert extract_ast_diff_features(sec).security_sensitive_annotation_removed

    raises = _parse(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1 +1,2 @@\n base\n+raise ValueError\n"
    )
    assert extract_ast_diff_features(raises).raises_new_exception


def test_fallback_confidence_and_generated() -> None:
    gen = _parse(
        "diff --git a/api/items_pb2.py b/api/items_pb2.py\n"
        "--- a/api/items_pb2.py\n+++ b/api/items_pb2.py\n"
        "@@ -1 +1 @@\n-a\n+b\n"
    )
    feats = extract_ast_diff_features(gen, fallback=True)
    assert feats.confidence == ConfidenceLevel.HEURISTIC
    assert feats.generated_or_stub_flag


def test_other_when_empty() -> None:
    diff = _parse("")
    feats = extract_ast_diff_features(diff)
    assert feats.edit_operation == EditOperation.OTHER
    assert feats.touched_symbol_count == 0


def test_class_def_kind() -> None:
    diff = _parse(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -1 +1,2 @@\n+class K:\n+    pass\n"
    )
    feats = extract_ast_diff_features(diff)
    assert "class_def" in feats.changed_node_kinds
