"""Tests for diff_parser."""

from __future__ import annotations

from llm_sca_tooling.patch_review.diff_parser import parse_unified_diff


def test_parse_basic(safe_diff: str) -> None:
    record = parse_unified_diff(safe_diff)
    assert record.diff_id.startswith("diff:")
    assert record.changed_files == ["src/util.py"]
    assert len(record.hunks) == 1
    assert record.added_lines >= 1
    assert record.removed_lines >= 1


def test_parse_supplied_diff_id() -> None:
    record = parse_unified_diff("", diff_id="diff:custom")
    assert record.diff_id == "diff:custom"
    assert record.hunks == []
    assert record.changed_files == []


def test_parse_multifile_and_provenance() -> None:
    diff = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n"
        "@@ -1 +1,2 @@\n line\n+added\n"
        "diff --git a/b.py b/b.py\n--- a/b.py\n+++ b/b.py\n"
        "@@ -1 +1 @@\n-old\n+new\n"
    )
    record = parse_unified_diff(
        diff, snapshot_before_id="s1", snapshot_after_id="s2", provenance={"r": "x"}
    )
    assert record.changed_files == ["a.py", "b.py"]
    assert record.snapshot_before_id == "s1"
    assert record.provenance == {"r": "x"}


def test_parse_malformed_header_records_diagnostic() -> None:
    diff = "diff --git brokenline\n@@ -1 +1 @@\n+new\n"
    record = parse_unified_diff(diff)
    assert any(d["code"] == "malformed_diff_header" for d in record.diagnostics)


def test_parse_hunk_without_file_diag() -> None:
    diff = "@@ -1 +1 @@\n+orphan\n"
    record = parse_unified_diff(diff)
    assert any(d["code"] == "hunk_without_file" for d in record.diagnostics)


def test_parse_dev_null_target_skipped() -> None:
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ /dev/null\n"
    record = parse_unified_diff(diff)
    assert record.changed_files == ["a.py"]


def test_parse_type_error_for_non_string() -> None:
    import pytest

    with pytest.raises(TypeError):
        parse_unified_diff(123)  # type: ignore[arg-type]
