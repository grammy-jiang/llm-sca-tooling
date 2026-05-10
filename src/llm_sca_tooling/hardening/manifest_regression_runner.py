"""Released artefact manifest regression runner."""

from __future__ import annotations

from llm_sca_tooling.hardening.models import ManifestRegressionFinding
from llm_sca_tooling.schemas.base import JsonObject


class ManifestRegressionRunner:
    def compare(self, baseline: JsonObject, current: JsonObject) -> JsonObject:
        findings = [
            ManifestRegressionFinding(
                key=key,
                baseline_value=baseline.get(key),
                current_value=current.get(key),
                severity="breaking",
            )
            for key in sorted(set(baseline) | set(current))
            if baseline.get(key) != current.get(key)
        ]
        changed = [finding.key for finding in findings]
        classification = "breaking" if changed else "clean"
        return {
            "changed_items": changed,
            "findings": [finding.model_dump(mode="json") for finding in findings],
            "classification": classification,
            "blocks_release": classification == "breaking",
        }
