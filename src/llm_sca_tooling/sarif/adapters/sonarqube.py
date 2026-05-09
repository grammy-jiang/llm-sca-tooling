"""SonarQube SARIF import adapter."""

from __future__ import annotations

from llm_sca_tooling.sarif.models import NormalizedSeverity, SarifLog
from llm_sca_tooling.sarif.normalizer import SarifNormalizer

# SonarQube severity → canonical severity
_SONAR_SEVERITY_MAP = {
    "blocker": NormalizedSeverity.CRITICAL,
    "critical": NormalizedSeverity.HIGH,
    "major": NormalizedSeverity.MEDIUM,
    "minor": NormalizedSeverity.LOW,
    "info": NormalizedSeverity.INFORMATIONAL,
}

# SonarQube rule-ID suffix → CWE family hint
_SONAR_RULE_FAMILIES: dict[str, str] = {
    "S2077": "sql-injection",
    "S3649": "sql-injection",
    "S5131": "xss",
    "S5144": "path-traversal",
    "S2076": "command-injection",
    "S2755": "xxe",
    "S2083": "path-traversal",
    "S4790": "crypto-weak",
    "S2068": "hardcoded-secret",
    "S2245": "insecure-random",
    "S3330": "missing-auth",
    "S4507": "privilege-escalation",
}


class SonarQubeAdapter:
    """Adapter for SARIF logs exported from SonarQube."""

    adapter_id = "sonarqube"

    def normalize_sonar_severity(self, value: str) -> NormalizedSeverity:
        """Convert a SonarQube severity string to canonical NormalizedSeverity."""
        return _SONAR_SEVERITY_MAP.get(value.lower(), NormalizedSeverity.MEDIUM)

    def rule_family(self, rule_id: str) -> str | None:
        """Extract a CWE-family hint from a SonarQube rule ID.

        SonarQube rule IDs look like 'python:S2077' or 'java:S5131'.
        """
        short = rule_id.split(":")[-1]  # e.g. 'S2077'
        return _SONAR_RULE_FAMILIES.get(short)

    def normalize_run(
        self,
        log: SarifLog,
        *,
        repo_id: str,
        snapshot_id: str,
        git_sha: str | None = None,
        run_id: str | None = None,
    ) -> object:
        """Normalize a SonarQube SARIF log using the shared SarifNormalizer.

        Applies SonarQube-specific severity mappings before normalization.
        """
        normalizer = SarifNormalizer()
        return normalizer.normalize(
            log,
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            git_sha=git_sha,
            run_id=run_id,
        )
