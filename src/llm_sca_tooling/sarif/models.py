"""SARIF v2.1.0 and normalized static-analysis models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "AlertChange",
    "AlertLocation",
    "NormalizedAlert",
    "NormalizedRule",
    "NormalizedSarifRun",
    "NormalizedSeverity",
    "SarifArtifactLocation",
    "SarifDelta",
    "SarifDeltaSummary",
    "SarifLocation",
    "SarifLog",
    "SarifPhysicalLocation",
    "SarifRegion",
    "SarifReportingDescriptor",
    "SarifResult",
    "SarifRun",
    "SarifTool",
    "SarifToolComponent",
]


class StrictSarifModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NormalizedSeverity(str, Enum):
    informational = "informational"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class SarifRegion(StrictSarifModel):
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    byte_offset: int | None = None
    byte_length: int | None = None
    snippet_text: str | None = None


class SarifArtifactLocation(StrictSarifModel):
    uri: str | None = None
    uri_base_id: str | None = None
    index: int | None = None
    resolved_path: str | None = None


class SarifPhysicalLocation(StrictSarifModel):
    artifact_location: SarifArtifactLocation | None = None
    region: SarifRegion | None = None


class SarifLocation(StrictSarifModel):
    physical_location: SarifPhysicalLocation | None = None
    message: str | None = None


class SarifReportingDescriptor(StrictSarifModel):
    id: str
    name: str | None = None
    short_description: str | None = None
    full_description: str | None = None
    help_uri: str | None = None
    default_level: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class SarifToolComponent(StrictSarifModel):
    name: str
    version: str | None = None
    semantic_version: str | None = None
    guid: str | None = None
    rules: list[SarifReportingDescriptor] = Field(default_factory=list)


class SarifTool(StrictSarifModel):
    driver: SarifToolComponent
    extensions: list[SarifToolComponent] = Field(default_factory=list)


class SarifResult(StrictSarifModel):
    rule_id: str | None = None
    rule_index: int | None = None
    level: str | None = None
    message: str
    locations: list[SarifLocation] = Field(default_factory=list)
    related_locations: list[SarifLocation] = Field(default_factory=list)
    baseline_state: str | None = None
    fingerprints: dict[str, str] = Field(default_factory=dict)
    partial_fingerprints: dict[str, str] = Field(default_factory=dict)
    suppressions: list[dict[str, Any]] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class SarifRun(StrictSarifModel):
    tool: SarifTool
    results: list[SarifResult] = Field(default_factory=list)
    original_uri_base_ids: dict[str, str] = Field(default_factory=dict)
    invocation_successful: bool = True
    invocation_exit_code: int | None = None


class SarifLog(StrictSarifModel):
    version: str
    schema_uri: str | None = None
    runs: list[SarifRun] = Field(default_factory=list)


class AlertLocation(StrictSarifModel):
    file_path: str | None = None
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    message: str | None = None


class NormalizedRule(StrictSarifModel):
    rule_id: str
    analyser_id: str
    name: str | None = None
    short_description: str | None = None
    full_description: str | None = None
    help_uri: str | None = None
    raw_severity: str | None = None
    normalized_severity: NormalizedSeverity
    cwe_ids: list[str] = Field(default_factory=list)
    owasp_categories: list[str] = Field(default_factory=list)
    rule_family: str = "other"
    predicate_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    confidence_level: str = "heuristic"


class NormalizedAlert(StrictSarifModel):
    alert_id: str
    run_id: str
    rule_id: str
    analyser_id: str
    raw_level: str | None = None
    normalized_severity: NormalizedSeverity
    message: str
    file_path: str | None = None
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    related_locations: list[AlertLocation] = Field(default_factory=list)
    suppressed: bool = False
    suppression_kind: str | None = None
    suppression_status: str | None = None
    suppression_justification: str | None = None
    fingerprint: str
    partial_fingerprint: str
    raw_fingerprints: dict[str, str] = Field(default_factory=dict)
    baseline_state: str | None = None
    bound_file_node_id: str | None = None
    bound_symbol_node_ids: list[str] = Field(default_factory=list)
    binding_confidence: str = "none"
    properties: dict[str, Any] = Field(default_factory=dict)


class NormalizedSarifRun(StrictSarifModel):
    run_id: str
    repo_id: str
    snapshot_id: str
    git_sha: str
    worktree_snapshot_id: str | None = None
    analyser_id: str
    analyser_version: str | None = None
    analyser_name: str
    ruleset_id: str
    ruleset_name: str | None = None
    invocation_start_ts: str | None = None
    invocation_end_ts: str | None = None
    invocation_exit_code: int | None = None
    invocation_successful: bool = True
    rules: list[NormalizedRule] = Field(default_factory=list)
    alerts: list[NormalizedAlert] = Field(default_factory=list)
    invocation_diagnostics: list[str] = Field(default_factory=list)
    raw_sarif_artifact_ref: str | None = None
    produced_by_run_id: str | None = None
    delta_from_run_id: str | None = None


class AlertChange(StrictSarifModel):
    before_alert: NormalizedAlert
    after_alert: NormalizedAlert
    change_type: str


class SarifDeltaSummary(StrictSarifModel):
    appeared_count: int
    disappeared_count: int
    unchanged_count: int
    changed_count: int
    appeared_by_severity: dict[str, int] = Field(default_factory=dict)
    disappeared_by_severity: dict[str, int] = Field(default_factory=dict)
    new_critical_or_high_count: int
    fixed_critical_or_high_count: int


class SarifDelta(StrictSarifModel):
    delta_id: str
    before_run_id: str
    after_run_id: str
    repo_id: str
    before_snapshot_id: str
    after_snapshot_id: str
    appeared: list[NormalizedAlert] = Field(default_factory=list)
    disappeared: list[NormalizedAlert] = Field(default_factory=list)
    unchanged: list[NormalizedAlert] = Field(default_factory=list)
    changed: list[AlertChange] = Field(default_factory=list)
    suppressed_in_before: list[NormalizedAlert] = Field(default_factory=list)
    suppressed_in_after: list[NormalizedAlert] = Field(default_factory=list)
    computed_ts: str

    @property
    def summary(self) -> SarifDeltaSummary:
        appeared_high = sum(
            1
            for alert in self.appeared
            if alert.normalized_severity.value in {"critical", "high"}
        )
        fixed_high = sum(
            1
            for alert in self.disappeared
            if alert.normalized_severity.value in {"critical", "high"}
        )
        return SarifDeltaSummary(
            appeared_count=len(self.appeared),
            disappeared_count=len(self.disappeared),
            unchanged_count=len(self.unchanged),
            changed_count=len(self.changed),
            appeared_by_severity=_severity_counts(self.appeared),
            disappeared_by_severity=_severity_counts(self.disappeared),
            new_critical_or_high_count=appeared_high,
            fixed_critical_or_high_count=fixed_high,
        )


def _severity_counts(alerts: list[NormalizedAlert]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for alert in alerts:
        key = alert.normalized_severity.value
        counts[key] = counts.get(key, 0) + 1
    return counts
