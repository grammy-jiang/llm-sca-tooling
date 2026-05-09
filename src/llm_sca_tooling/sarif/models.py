"""SARIF v2.1.0 and normalized static-analysis evidence models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, id_field, validate_repo_relative_path
from llm_sca_tooling.schemas.provenance import ArtifactRef


class NormalizedSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


SEVERITY_RANK = {
    NormalizedSeverity.INFORMATIONAL: 0,
    NormalizedSeverity.LOW: 1,
    NormalizedSeverity.MEDIUM: 2,
    NormalizedSeverity.HIGH: 3,
    NormalizedSeverity.CRITICAL: 4,
}


class AlertChangeType(StrEnum):
    LOCATION_SHIFTED = "location_shifted"
    SEVERITY_CHANGED = "severity_changed"
    MESSAGE_CHANGED = "message_changed"
    SUPPRESSION_CHANGED = "suppression_changed"


class SarifReportingConfiguration(StrictBaseModel):
    enabled: bool = True
    level: str | None = None
    rank: float | None = None


class SarifReportingDescriptor(StrictBaseModel):
    id: str = Field(min_length=1)
    name: str | None = None
    short_description: str | None = None
    full_description: str | None = None
    help_uri: str | None = None
    default_configuration: SarifReportingConfiguration | None = None
    properties: JsonObject = Field(default_factory=dict)


class SarifReportingDescriptorReference(StrictBaseModel):
    id: str | None = None
    index: int | None = None


class SarifToolComponent(StrictBaseModel):
    name: str = Field(min_length=1)
    version: str | None = None
    semantic_version: str | None = None
    guid: str | None = None
    rules: list[SarifReportingDescriptor] = Field(default_factory=list)
    notifications: list[SarifReportingDescriptor] = Field(default_factory=list)


class SarifTool(StrictBaseModel):
    driver: SarifToolComponent
    extensions: list[SarifToolComponent] = Field(default_factory=list)


class SarifArtifactLocation(StrictBaseModel):
    uri: str | None = None
    uri_base_id: str | None = None
    index: int | None = None
    resolved_path: str | None = None
    unresolvable: bool = False

    @field_validator("resolved_path")
    @classmethod
    def validate_resolved_path(cls, value: str | None) -> str | None:
        return None if value is None else validate_repo_relative_path(value)


class SarifRegion(StrictBaseModel):
    start_line: int | None = Field(default=None, ge=1)
    start_column: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    end_column: int | None = Field(default=None, ge=1)
    byte_offset: int | None = Field(default=None, ge=0)
    byte_length: int | None = Field(default=None, ge=0)
    snippet_text: str | None = None


class SarifPhysicalLocation(StrictBaseModel):
    artifact_location: SarifArtifactLocation
    region: SarifRegion | None = None


class SarifLogicalLocation(StrictBaseModel):
    name: str | None = None
    fully_qualified_name: str | None = None
    kind: str | None = None
    properties: JsonObject = Field(default_factory=dict)


class SarifLocation(StrictBaseModel):
    physical_location: SarifPhysicalLocation | None = None
    logical_locations: list[SarifLogicalLocation] = Field(default_factory=list)
    message: str | None = None


class SarifThreadFlowLocation(StrictBaseModel):
    location: SarifLocation | None = None
    kinds: list[str] = Field(default_factory=list)
    state: JsonObject = Field(default_factory=dict)


class SarifThreadFlow(StrictBaseModel):
    locations: list[SarifThreadFlowLocation] = Field(default_factory=list)


class SarifCodeFlow(StrictBaseModel):
    thread_flows: list[SarifThreadFlow] = Field(default_factory=list)
    message: str | None = None


class SarifArtifactChange(StrictBaseModel):
    artifact_location: SarifArtifactLocation | None = None
    replacements: list[JsonObject] = Field(default_factory=list)


class SarifFix(StrictBaseModel):
    description: str | None = None
    artifact_changes: list[SarifArtifactChange] = Field(default_factory=list)


class SarifSuppression(StrictBaseModel):
    kind: str
    status: str | None = None
    justification: str | None = None


class SarifResult(StrictBaseModel):
    rule_id: str | None = None
    rule_index: int | None = None
    level: str | None = None
    message: str
    locations: list[SarifLocation] = Field(default_factory=list)
    related_locations: list[SarifLocation] = Field(default_factory=list)
    code_flows: list[SarifCodeFlow] = Field(default_factory=list)
    fixes: list[SarifFix] = Field(default_factory=list)
    suppressions: list[SarifSuppression] = Field(default_factory=list)
    baseline_state: str | None = None
    fingerprints: dict[str, str] = Field(default_factory=dict)
    partial_fingerprints: dict[str, str] = Field(default_factory=dict)
    work_item_uris: list[str] = Field(default_factory=list)
    properties: JsonObject = Field(default_factory=dict)


class SarifArtifact(StrictBaseModel):
    location: SarifArtifactLocation
    parent_index: int | None = None
    length: int | None = Field(default=None, ge=0)
    mime_type: str | None = None


class SarifNotification(StrictBaseModel):
    message: str
    level: str | None = None
    associated_rule: SarifReportingDescriptorReference | None = None


class SarifInvocation(StrictBaseModel):
    tool_execution_successful: bool | None = None
    exit_code: int | None = None
    start_time_utc: str | None = None
    end_time_utc: str | None = None
    working_directory: SarifArtifactLocation | None = None
    tool_execution_notifications: list[SarifNotification] = Field(default_factory=list)


class SarifRunAutomationDetails(StrictBaseModel):
    id: str | None = None
    guid: str | None = None


class SarifRun(StrictBaseModel):
    tool: SarifTool
    results: list[SarifResult] = Field(default_factory=list)
    artifacts: list[SarifArtifact] = Field(default_factory=list)
    logical_locations: list[SarifLogicalLocation] = Field(default_factory=list)
    invocations: list[SarifInvocation] = Field(default_factory=list)
    automation_details: SarifRunAutomationDetails | None = None
    baseline_guid: str | None = None
    original_uri_base_ids: dict[str, str] = Field(default_factory=dict)
    properties: JsonObject = Field(default_factory=dict)


class SarifLog(StrictBaseModel):
    version: Literal["2.1.0"]
    runs: list[SarifRun] = Field(default_factory=list)
    schema_uri: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


class AlertLocation(StrictBaseModel):
    file_path: str | None = None
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    message: str | None = None


class AlertCodeFlow(StrictBaseModel):
    locations: list[AlertLocation] = Field(default_factory=list)
    message: str | None = None


class NormalizedRule(StrictBaseModel):
    rule_id: str = Field(min_length=1)
    analyser_id: str = Field(min_length=1)
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
    confidence_level: str = "parser"
    properties: JsonObject = Field(default_factory=dict)


class NormalizedAlert(StrictBaseModel):
    alert_id: str = id_field("Fingerprint-derived stable alert identifier.")
    run_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    analyser_id: str = Field(min_length=1)
    raw_level: str | None = None
    normalized_severity: NormalizedSeverity
    message: str
    file_path: str | None = None
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    related_locations: list[AlertLocation] = Field(default_factory=list)
    code_flows: list[AlertCodeFlow] = Field(default_factory=list)
    suppressed: bool = False
    suppression_kind: str | None = None
    suppression_status: str | None = None
    suppression_justification: str | None = None
    fingerprint: str = Field(min_length=1)
    partial_fingerprint: str | None = None
    raw_fingerprints: dict[str, str] = Field(default_factory=dict)
    baseline_state: str | None = None
    bound_file_node_id: str | None = None
    bound_symbol_node_ids: list[str] = Field(default_factory=list)
    binding_confidence: str = "none"
    properties: JsonObject = Field(default_factory=dict)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str | None) -> str | None:
        return None if value is None else validate_repo_relative_path(value)


class NormalizedSarifRun(StrictBaseModel):
    run_id: str = id_field("SARIF run identifier.")
    repo_id: str
    snapshot_id: str
    git_sha: str | None = None
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
    raw_sarif_artifact_ref: ArtifactRef | None = None
    produced_by_run_id: str | None = None
    delta_from_run_id: str | None = None


class AlertChange(StrictBaseModel):
    before_alert: NormalizedAlert
    after_alert: NormalizedAlert
    change_type: AlertChangeType


class SarifDeltaSummary(StrictBaseModel):
    appeared_count: int
    disappeared_count: int
    unchanged_count: int
    changed_count: int
    appeared_by_severity: dict[str, int]
    disappeared_by_severity: dict[str, int]
    new_critical_or_high_count: int
    fixed_critical_or_high_count: int


class SarifDelta(StrictBaseModel):
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
    delta_id: str
    computed_ts: str

    @property
    def summary(self) -> SarifDeltaSummary:
        return SarifDeltaSummary(
            appeared_count=len(self.appeared),
            disappeared_count=len(self.disappeared),
            unchanged_count=len(self.unchanged),
            changed_count=len(self.changed),
            appeared_by_severity=_severity_counts(self.appeared),
            disappeared_by_severity=_severity_counts(self.disappeared),
            new_critical_or_high_count=sum(1 for alert in self.appeared if alert.normalized_severity in {NormalizedSeverity.CRITICAL, NormalizedSeverity.HIGH}),
            fixed_critical_or_high_count=sum(1 for alert in self.disappeared if alert.normalized_severity in {NormalizedSeverity.CRITICAL, NormalizedSeverity.HIGH}),
        )


def _severity_counts(alerts: list[NormalizedAlert]) -> dict[str, int]:
    counts = {severity.value: 0 for severity in NormalizedSeverity}
    for alert in alerts:
        counts[alert.normalized_severity.value] += 1
    return counts

