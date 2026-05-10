"""Sanity tests for the sast-repair skill template."""

from __future__ import annotations

from pathlib import Path

SKILL_PATH = Path(__file__).resolve().parents[2] / ".skills" / "sast_repair.SKILL.md"


def test_skill_file_exists() -> None:
    assert SKILL_PATH.is_file()


def test_skill_front_matter_and_sections() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "name: sast-repair" in text
    assert "version: 0.1.0" in text
    for header in (
        "## When to use",
        "## When NOT to use",
        "## Steps",
        "## Verification",
        "## Stop Conditions",
        "## Examples",
    ):
        assert header in text, f"missing section: {header}"


def test_skill_includes_verdict_mappings() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    for verdict in (
        "alert_fixed",
        "alert_fixed_with_risk",
        "repair_failed",
        "repair_blocked",
        "false_positive_suppressed",
    ):
        assert verdict in text
