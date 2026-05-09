"""SonarQube SARIF import helper."""

from __future__ import annotations

from llm_sca_tooling.sarif.normalizer import normalize_severity


class SonarQubeAdapter:
    adapter_id = "sonarqube"

    def normalize_sonar_severity(self, value: str):
        return normalize_severity(self.adapter_id, value, {})

