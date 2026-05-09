from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.sarif.errors import SarifParseError, SarifVersionError
from llm_sca_tooling.sarif.fingerprint import compute_alert_fingerprint
from llm_sca_tooling.sarif.models import NormalizedSeverity
from llm_sca_tooling.sarif.normalizer import (
    SarifNormalizer,
    extract_cwe_ids,
    normalize_rule_family,
    normalize_severity,
)
from llm_sca_tooling.sarif.parser import SarifParser


def test_parser_accepts_v21_and_resolves_uri_base(
    sarif_fixtures: Path, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "pkg").mkdir(parents=True)
    log = SarifParser().parse_file(
        sarif_fixtures / "external_generic.sarif.json", repo_root=repo
    )
    result = log.runs[0].results[0]
    assert (
        result.locations[0].physical_location.artifact_location.resolved_path
        == "src/pkg/core.py"
    )
    assert result.fingerprints["primaryLocationLineHash"] == "existing-fingerprint"


def test_parser_rejects_wrong_version_and_malformed(sarif_fixtures: Path) -> None:
    with pytest.raises(SarifVersionError):
        SarifParser().parse_file(sarif_fixtures / "wrong_version.sarif.json")
    with pytest.raises(SarifParseError):
        SarifParser().parse_file(sarif_fixtures / "malformed.sarif.json")


def test_result_without_location_is_preserved(sarif_fixtures: Path) -> None:
    log = SarifParser().parse_file(sarif_fixtures / "partial_locations.sarif.json")
    assert log.runs[0].results[0].locations == []


def test_normalizer_maps_severity_cwe_family_and_predicates(
    sarif_fixtures: Path,
) -> None:
    assert normalize_severity("semgrep", "error", {}) == NormalizedSeverity.HIGH
    assert (
        normalize_severity("semgrep", "warning", {"security-severity": "9.5"})
        == NormalizedSeverity.CRITICAL
    )
    assert (
        normalize_severity(
            "bandit", "warning", {"issue_severity": "HIGH", "issue_confidence": "HIGH"}
        )
        == NormalizedSeverity.HIGH
    )
    assert (
        normalize_severity(
            "bandit", "warning", {"issue_severity": "LOW", "issue_confidence": "LOW"}
        )
        == NormalizedSeverity.LOW
    )
    assert normalize_severity("codeql", "warning", {}) == NormalizedSeverity.MEDIUM
    assert normalize_severity("unknown", "error", {}) == NormalizedSeverity.HIGH
    assert extract_cwe_ids({"cwe": ["CWE-89", "cwe: 79", "89"]}) == ["CWE-79", "CWE-89"]
    assert (
        normalize_rule_family("rule", cwe_ids=["CWE-89"], tags=[], description="")
        == "sql-injection"
    )
    assert (
        normalize_rule_family(
            "python.lang.security.audit.sqli", tags=[], cwe_ids=[], description=""
        )
        == "sql-injection"
    )
    assert (
        normalize_rule_family("B105", tags=[], cwe_ids=[], description="")
        == "hardcoded-secret"
    )
    codeql = SarifNormalizer().normalize(
        SarifParser().parse_file(sarif_fixtures / "codeql_basic.sarif.json"),
        repo_id="repo:test",
        snapshot_id="snap:test",
        git_sha="abc",
        analyser_hint="codeql",
    )
    assert codeql.rules[0].predicate_id == "42"


def test_fingerprint_stability_and_sensitivity() -> None:
    base = compute_alert_fingerprint(
        analyser_id="semgrep",
        rule_id="r1",
        file_path="a.py",
        message="hello   world",
        snippet="x",
    )
    assert base == compute_alert_fingerprint(
        analyser_id="semgrep",
        rule_id="r1",
        file_path="a.py",
        message="hello world",
        snippet="x",
    )
    assert base != compute_alert_fingerprint(
        analyser_id="semgrep",
        rule_id="r2",
        file_path="a.py",
        message="hello world",
        snippet="x",
    )
    assert base != compute_alert_fingerprint(
        analyser_id="semgrep",
        rule_id="r1",
        file_path="b.py",
        message="hello world",
        snippet="x",
    )
    assert base != compute_alert_fingerprint(
        analyser_id="semgrep",
        rule_id="r1",
        file_path="a.py",
        message="different",
        snippet="x",
    )
    assert base != compute_alert_fingerprint(
        analyser_id="semgrep",
        rule_id="r1",
        file_path="a.py",
        message="hello world",
        snippet="y",
    )
