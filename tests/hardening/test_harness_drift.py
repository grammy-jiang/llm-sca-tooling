"""Tests for HarnessDriftChecker."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.hardening.harness_drift import HarnessDriftChecker


def test_check_returns_drift_report(tmp_path: Path) -> None:
    checker = HarnessDriftChecker(repo_root=str(tmp_path))
    report = checker.check(stage="S0")
    assert hasattr(report, "records")
    assert hasattr(report, "is_clean")


def test_missing_agents_md_flagged(tmp_path: Path) -> None:
    # No files created — AGENTS.md is missing
    checker = HarnessDriftChecker(repo_root=str(tmp_path))
    report = checker.check(stage="S0")
    assert report.has_missing


def test_present_managed_agents_md_is_clean(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("<!-- local-agent-harness:auto -->\n# AGENTS\n")
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    checker = HarnessDriftChecker(repo_root=str(tmp_path))
    report = checker.check(stage="S0")
    # All required files present and managed marker present
    assert not report.has_missing


def test_is_clean_property_on_empty_records(tmp_path: Path) -> None:
    checker = HarnessDriftChecker(repo_root=str(tmp_path))
    report = checker.check(stage="S0")
    # Whether clean or not, is_clean is a bool
    assert isinstance(report.is_clean, bool)
