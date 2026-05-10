"""Typed contracts for Phase 19 hardening."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


def utc_now_ts() -> str:
    """Return an RFC3339-ish UTC timestamp without importing higher layers."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class HardenedPermissionMode(StrEnum):
    READ_ONLY = "read_only"
    READ_SEARCH = "read_search"
    READ_SEARCH_EDIT = "read_search_edit"
    READ_SEARCH_EXECUTE = "read_search_execute"
    REVIEW = "review"
    COMMIT = "commit"


class PermissionProfile(StrictBaseModel):
    mode: HardenedPermissionMode
    read: bool = False
    search: bool = False
    edit: bool = False
    execute: bool = False
    review: bool = False
    commit: bool = False


class PermissionProfileSet(StrictBaseModel):
    default_mode: HardenedPermissionMode = HardenedPermissionMode.READ_SEARCH
    per_repo_overrides: dict[str, HardenedPermissionMode] = Field(default_factory=dict)
    per_workflow_overrides: dict[str, HardenedPermissionMode] = Field(
        default_factory=dict
    )
    network_policy: str = "deny-by-default"
    path_allowlist: list[str] = Field(default_factory=list)
    execute_allowlist: list[str] = Field(default_factory=list)
    review_allowlist: list[str] = Field(default_factory=list)
    commit_allowlist: list[str] = Field(default_factory=list)


class TaskAuthorizationDecision(StrictBaseModel):
    allowed: bool
    reason: str
    ttl_seconds: int


class CacheInvalidationEvent(StrictBaseModel):
    event_id: str = Field(min_length=1)
    repo_id: str = Field(min_length=1)
    git_sha: str = Field(min_length=1)
    changed_files: list[str] = Field(default_factory=list)
    invalidated_keys: list[str] = Field(default_factory=list)
    ts: str = Field(default_factory=utc_now_ts)


class GraphChunk(StrictBaseModel):
    chunk_id: str = Field(min_length=1)
    node_ids: list[str]
    module_prefix: str = ""
    artifact_ref: str | None = None


class SubscriptionRecoveryState(StrictBaseModel):
    client_id: str = Field(min_length=1)
    resource_uri: str = Field(min_length=1)
    last_seen_ts: str = Field(min_length=1)
    authorization_context_hash: str | None = None


class CumulativeRiskPattern(StrEnum):
    REPEATED_IDENTICAL_TOOL_CALLS = "repeated_identical_tool_calls"
    REPEATED_FAILING_GATE_NO_CHANGE = "repeated_failing_gate_no_change"
    CONTEXT_GROWTH_NO_EVIDENCE = "context_growth_no_evidence"
    DENIED_OPERATION_STORM = "denied_operation_storm"
    BUDGET_EXHAUSTION_PATTERN = "budget_exhaustion_pattern"
    SUSPICIOUS_MULTISTEP = "suspicious_multistep"


class CumulativeRiskEvent(StrictBaseModel):
    event_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    pattern_type: CumulativeRiskPattern
    contributing_events: list[str] = Field(default_factory=list)
    risk_score: float = Field(ge=0.0, le=1.0)
    threshold_exceeded: bool
    action_taken: str = "logged"
    ts: str = Field(default_factory=utc_now_ts)


class DriftClassification(StrEnum):
    CLEAN = "clean"
    STALE = "stale"
    MISSING = "missing"
    RELAXED = "relaxed"
    OUT_OF_STAGE = "out-of-stage"


class HarnessDriftRecord(StrictBaseModel):
    artifact_path: str = Field(min_length=1)
    classification: DriftClassification
    detail: str = ""
    waiver_ref: str | None = None
    checked_ts: str = Field(default_factory=utc_now_ts)


class ManifestRegressionFinding(StrictBaseModel):
    key: str = Field(min_length=1)
    baseline_value: JsonObject | str | int | float | bool | None = None
    current_value: JsonObject | str | int | float | bool | None = None
    severity: str = "breaking"


class TraceRedactionAuditResult(StrictBaseModel):
    passed: bool
    findings: list[JsonObject] = Field(default_factory=list)


class HTTPTransportConfig(StrictBaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1, le=65535)
    tls_enabled: bool = False
    tls_cert_path: str | None = None
    tls_key_path: str | None = None
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1"]
    )
    auth_token_env_var: str | None = None
    rate_limit_requests_per_minute: int = Field(default=60, ge=1)
    max_connections: int = Field(default=16, ge=1)
    single_user: bool = True

    @field_validator("cors_allowed_origins")
    @classmethod
    def reject_wildcard_cors(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("wildcard CORS origin is rejected")
        return value

    @model_validator(mode="after")
    def validate_security(self) -> HTTPTransportConfig:
        if self.host not in {"127.0.0.1", "localhost"} and not self.tls_enabled:
            raise ValueError("TLS is required for non-localhost HTTP transport")
        if not self.single_user and not self.auth_token_env_var:
            raise ValueError("auth token env var is required when single_user is false")
        return self
