"""Phase 16 trace models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm_sca_tooling.evaluation.models import now_ts


class StrictTraceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Contract and scope ────────────────────────────────────────────────────────


class ScopeFilter(StrictTraceModel):
    include_modules: list[str] = Field(default_factory=list)
    include_files: list[str] = Field(default_factory=list)
    include_functions: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    max_call_depth: int = 10
    trace_stdlib: bool = False
    trace_third_party: bool = False
    derived_from_fl_result: bool = False
    derived_from_changed_symbols: bool = False


class TraceRunContract(StrictTraceModel):
    contract_id: str
    command: str
    args: list[str] = Field(default_factory=list)
    timeout_seconds: int = 30
    environment_snapshot: dict[str, Any] = Field(default_factory=dict)
    working_dir: str = "."
    scope_filter: ScopeFilter
    redaction_policy: str = "default"
    max_raw_trace_bytes: int = 10 * 1024 * 1024
    max_compressed_events: int = 50
    language: str = "python"
    adapter_id: str = "python"
    sandbox_required: bool = True


# ── Raw trace artefact ────────────────────────────────────────────────────────


class TraceEvent(StrictTraceModel):
    event_id: str
    event_type: str
    module: str
    function: str
    file_path: str
    line_number: int = 0
    depth: int = 0
    arg_type_hints: list[str] = Field(default_factory=list)
    return_type_hash: str | None = None
    exception_type: str | None = None
    exception_message_redacted: bool = False
    ts_ns: int = 0
    redaction_applied: bool = True


class RawTraceArtefact(StrictTraceModel):
    artefact_id: str
    trace_run_id: str
    language: str
    adapter_version: str
    events_jsonl_path: str
    event_count: int
    truncated: bool = False
    truncation_reason: str | None = None
    size_bytes: int = 0
    git_sha: str = "unknown"
    environment_snapshot_hash: str = "unknown"
    redaction_policy_hash: str = "default"
    created_ts: str = Field(default_factory=now_ts)


# ── Compression ───────────────────────────────────────────────────────────────


class StateDiff(StrictTraceModel):
    trace_run_id: str
    function_path: str
    parameter_before: str | None = None
    parameter_after: str | None = None
    return_before: str | None = None
    return_after: str | None = None
    side_effect_detected: bool = False
    diff_type: str
    confidence: str = "heuristic"


class DivergencePoint(StrictTraceModel):
    trace_run_id: str
    function_path: str
    file_path: str
    line_number: int = 0
    divergence_type: str
    pre_fix_event_ref: str | None = None
    post_fix_event_ref: str | None = None
    graph_node_id: str | None = None
    confidence: str = "heuristic"
    notes: str = ""


class CompressedTrace(StrictTraceModel):
    trace_run_id: str
    raw_artefact_id: str
    executed_path_summary: str
    relevant_events: list[TraceEvent] = Field(default_factory=list)
    state_diffs: list[StateDiff] = Field(default_factory=list)
    divergence_points: list[DivergencePoint] = Field(default_factory=list)
    exception_events: list[TraceEvent] = Field(default_factory=list)
    compressed_token_estimate: int = 0
    compression_ratio: float = 1.0
    scope_coverage: float = 0.0
    uncertainty_notes: list[str] = Field(default_factory=list)
    summarizer_model: str = "null"
    confidence: str = "unknown"


# ── Result ────────────────────────────────────────────────────────────────────


class TraceRunResult(StrictTraceModel):
    trace_run_id: str
    contract_id: str
    language: str
    adapter_id: str
    status: str
    raw_artefact_ref: str | None = None
    compressed_trace_ref: str | None = None
    state_diffs: list[StateDiff] = Field(default_factory=list)
    divergence_points: list[DivergencePoint] = Field(default_factory=list)
    non_reproducing: bool = False
    harness_condition_id: str
    run_id: str
    wall_ms: int = 0
    diagnostics: list[str] = Field(default_factory=list)
