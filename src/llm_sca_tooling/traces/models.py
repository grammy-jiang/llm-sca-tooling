"""Pydantic contracts for Phase 16 trace capture."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, id_field


class TraceLanguage(StrEnum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    CPP = "cpp"
    C = "c"


class TraceEventType(StrEnum):
    CALL = "call"
    RETURN = "return"
    EXCEPTION = "exception"
    LINE = "line"


class TraceRunStatus(StrEnum):
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    SCOPE_EMPTY = "scope_empty"
    OUT_OF_SCOPE = "out_of_scope"
    NOT_IMPLEMENTED = "not_implemented"
    TRUNCATED = "truncated"
    NOT_REPRODUCING = "not_reproducing"
    FAILED = "failed"


class TraceDiffType(StrEnum):
    VALUE_CHANGE = "value_change"
    EXCEPTION_VS_RETURN = "exception_vs_return"
    PATH_DIVERGENCE = "path_divergence"
    NEW_CALL = "new_call"
    MISSING_CALL = "missing_call"


class TraceDivergenceType(StrEnum):
    BRANCH_TAKEN_VS_NOT_TAKEN = "branch_taken_vs_not_taken"
    EXCEPTION_RAISED_VS_NOT = "exception_raised_vs_not"
    RETURN_VALUE_TYPE_MISMATCH = "return_value_type_mismatch"
    CALL_ORDER_CHANGE = "call_order_change"
    MISSING_CALL = "missing_call"
    NEW_CALL = "new_call"


class TraceConfidence(StrEnum):
    ANALYSER = "analyser"
    HEURISTIC = "heuristic"
    TRACE = "trace"
    UNKNOWN = "unknown"


class ScopeFilter(StrictBaseModel):
    include_modules: list[str] = Field(default_factory=list)
    include_files: list[str] = Field(default_factory=list)
    include_functions: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "tests/*",
            "test/*",
            "fixtures/*",
            "docs/*",
            ".github/*",
        ]
    )
    max_call_depth: int = Field(default=10, ge=0, le=100)
    trace_stdlib: bool = False
    trace_third_party: bool = False
    derived_from_fl_result: bool = False
    derived_from_changed_symbols: bool = False

    @property
    def is_empty(self) -> bool:
        return not (
            self.include_modules or self.include_files or self.include_functions
        )

    @field_validator("include_modules", "include_files", "include_functions")
    @classmethod
    def unique_values(cls, value: list[str]) -> list[str]:
        return [item for item in dict.fromkeys(v.strip() for v in value) if item]


class TraceRunContract(StrictBaseModel):
    contract_id: str = id_field("Trace contract identifier.")
    command: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(gt=0, le=3600)
    environment_snapshot: JsonObject = Field(default_factory=dict)
    working_dir: str = Field(min_length=1)
    scope_filter: ScopeFilter
    redaction_policy: JsonObject = Field(default_factory=dict)
    max_raw_trace_bytes: int = Field(default=1_000_000, ge=1)
    max_compressed_events: int = Field(default=50, ge=1, le=50)
    language: TraceLanguage = TraceLanguage.PYTHON
    adapter_id: str = Field(default="python-sys-settrace", min_length=1)
    sandbox_required: bool = True
    expected_failure: bool = False
    expected_exception_type: str | None = None
    trace_lines: bool = False

    @model_validator(mode="after")
    def validate_scope(self) -> TraceRunContract:
        if self.scope_filter.is_empty:
            raise ValueError(
                "scope_filter must include at least one module, file, or function"
            )
        return self


class TraceEvent(StrictBaseModel):
    event_id: str = id_field("Trace event identifier.")
    event_type: TraceEventType
    module: str = ""
    function: str = ""
    file_path: str = ""
    line_number: int = Field(default=0, ge=0)
    depth: int = Field(default=0, ge=0)
    arg_type_hints: dict[str, str] = Field(default_factory=dict)
    return_type_hash: str | None = None
    exception_type: str | None = None
    exception_message_redacted: bool = True
    ts_ns: int = Field(ge=0)
    redaction_applied: bool = True

    @property
    def function_path(self) -> str:
        if self.module and self.function:
            return f"{self.module}.{self.function}"
        return self.function or self.module or self.file_path


class RawTraceArtefact(StrictBaseModel):
    artefact_id: str = id_field("Raw trace artefact identifier.")
    trace_run_id: str = Field(min_length=1)
    language: TraceLanguage
    adapter_version: str = Field(min_length=1)
    events_jsonl_path: str = Field(min_length=1)
    event_count: int = Field(ge=0)
    truncated: bool = False
    truncation_reason: str | None = None
    size_bytes: int = Field(ge=0)
    git_sha: str | None = None
    environment_snapshot_hash: str = Field(min_length=1)
    redaction_policy_hash: str = Field(min_length=1)
    created_ts: str = Field(min_length=1)


class StateDiff(StrictBaseModel):
    trace_run_id: str = Field(min_length=1)
    function_path: str = Field(min_length=1)
    parameter_before: JsonObject = Field(default_factory=dict)
    parameter_after: JsonObject = Field(default_factory=dict)
    return_before: str | None = None
    return_after: str | None = None
    side_effect_detected: bool = False
    diff_type: TraceDiffType
    confidence: TraceConfidence = TraceConfidence.HEURISTIC


class DivergencePoint(StrictBaseModel):
    trace_run_id: str = Field(min_length=1)
    function_path: str = Field(min_length=1)
    file_path: str = ""
    line_number: int = Field(default=0, ge=0)
    divergence_type: TraceDivergenceType
    pre_fix_event_ref: str | None = None
    post_fix_event_ref: str | None = None
    graph_node_id: str | None = None
    confidence: TraceConfidence = TraceConfidence.HEURISTIC
    notes: str = ""


class CompressedTrace(StrictBaseModel):
    trace_run_id: str = Field(min_length=1)
    raw_artefact_id: str = Field(min_length=1)
    executed_path_summary: list[str] = Field(default_factory=list)
    relevant_events: list[TraceEvent] = Field(default_factory=list, max_length=50)
    state_diffs: list[StateDiff] = Field(default_factory=list)
    divergence_points: list[DivergencePoint] = Field(default_factory=list)
    exception_events: list[TraceEvent] = Field(default_factory=list, max_length=50)
    compressed_token_estimate: int = Field(default=0, ge=0)
    compression_ratio: float = Field(default=1.0, ge=0.0)
    scope_coverage: JsonObject = Field(default_factory=dict)
    uncertainty_notes: list[str] = Field(default_factory=list)
    summarizer_model: str = Field(min_length=1)
    confidence: TraceConfidence = TraceConfidence.UNKNOWN


class TraceRunResult(StrictBaseModel):
    trace_run_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    language: TraceLanguage
    adapter_id: str = Field(min_length=1)
    status: TraceRunStatus
    raw_artefact_ref: str | None = None
    compressed_trace_ref: str | None = None
    state_diffs: list[StateDiff] = Field(default_factory=list)
    divergence_points: list[DivergencePoint] = Field(default_factory=list)
    non_reproducing: bool = False
    harness_condition_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    wall_ms: int = Field(default=0, ge=0)
    diagnostics: list[JsonObject] = Field(default_factory=list)
