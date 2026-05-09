from __future__ import annotations

from pathlib import Path


def test_harness_docs_include_drift_classes() -> None:
    text = Path("docs/harness.md").read_text(encoding="utf-8")
    for drift_class in ["missing", "stale", "relaxed", "out-of-stage", "clean"]:
        assert drift_class in text


def test_harness_condition_template_is_available() -> None:
    assert Path("docs/harness-condition-sheet.md").exists()
