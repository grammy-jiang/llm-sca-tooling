"""Tests for the SonarQube SARIF adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.sarif.adapters.sonarqube import SonarQubeAdapter
from llm_sca_tooling.sarif.models import NormalizedSeverity

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sarif_runs"


def test_normalize_sonar_severity_blocker() -> None:
    adapter = SonarQubeAdapter()
    assert adapter.normalize_sonar_severity("BLOCKER") == NormalizedSeverity.CRITICAL


def test_normalize_sonar_severity_major() -> None:
    adapter = SonarQubeAdapter()
    assert adapter.normalize_sonar_severity("MAJOR") == NormalizedSeverity.MEDIUM


def test_rule_family_sql_injection() -> None:
    adapter = SonarQubeAdapter()
    assert adapter.rule_family("python:S2077") == "sql-injection"


def test_rule_family_unknown() -> None:
    adapter = SonarQubeAdapter()
    assert adapter.rule_family("python:S9999") is None


def test_normalize_run_with_fixture() -> None:
    from llm_sca_tooling.sarif.parser import SarifParser

    adapter = SonarQubeAdapter()
    fixture_path = FIXTURE_DIR / "sonarqube_export.sarif.json"
    if not fixture_path.exists():
        pytest.skip("sonarqube fixture not found")
    log = SarifParser().parse_file(fixture_path)
    result = adapter.normalize_run(
        log, repo_id="test-repo", snapshot_id="snap-1", git_sha=None
    )
    assert result is not None
