from __future__ import annotations

from llm_sca_tooling.sarif.adapters.bandit import bandit_json_to_sarif
from llm_sca_tooling.sarif.adapters.codeql import CODEQL_BACKEND_ENABLED, CodeQLAdapter
from llm_sca_tooling.sarif.adapters.ruleset import resolve_ruleset
from llm_sca_tooling.sarif.adapters.sonarqube import SonarQubeAdapter
from llm_sca_tooling.sarif.models import NormalizedSeverity
from llm_sca_tooling.sarif.parser import SarifParser


def test_ruleset_offline_rejects_registry_network(tmp_path) -> None:
    resolved = resolve_ruleset("p/security-audit", repo_root=tmp_path, offline=True)
    assert resolved.diagnostics == ["NETWORK_REQUIRED:p/security-audit"]


def test_bandit_json_fallback_is_valid_sarif() -> None:
    sarif = bandit_json_to_sarif(
        {
            "results": [
                {
                    "test_id": "B105",
                    "test_name": "hardcoded_password",
                    "issue_text": "secret",
                    "filename": "a.py",
                    "line_number": 1,
                    "issue_severity": "HIGH",
                    "issue_confidence": "HIGH",
                }
            ]
        }
    )
    log = SarifParser().parse_obj(sarif)
    assert log.runs[0].results[0].rule_id == "B105"


def test_codeql_disabled_by_default() -> None:
    assert CODEQL_BACKEND_ENABLED is False
    availability = CodeQLAdapter().check_availability()
    assert availability.available is False
    assert availability.diagnostics == ["CODEQL_BACKEND_DISABLED"]


def test_sonarqube_blocker_is_critical() -> None:
    assert (
        SonarQubeAdapter().normalize_sonar_severity("BLOCKER")
        == NormalizedSeverity.CRITICAL
    )
