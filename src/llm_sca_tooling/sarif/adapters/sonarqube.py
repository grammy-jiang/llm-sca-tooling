"""SonarQube SARIF normalization helper."""

from __future__ import annotations

from llm_sca_tooling.sarif.models import NormalizedSeverity
from llm_sca_tooling.sarif.normalizer import normalize_severity

__all__ = ["SonarQubeAdapter"]


class SonarQubeAdapter:
    adapter_id = "sonarqube"

    def normalize_level(self, level: str) -> NormalizedSeverity:
        return normalize_severity(self.adapter_id, level, {})
