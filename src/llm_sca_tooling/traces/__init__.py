"""Phase 16 dynamic trace augmentation."""

from llm_sca_tooling.traces.contract import (
    build_environment_snapshot,
    validate_command_allowlist,
)
from llm_sca_tooling.traces.models import (
    CompressedTrace,
    DivergencePoint,
    RawTraceArtefact,
    ScopeFilter,
    StateDiff,
    TraceEvent,
    TraceRunContract,
    TraceRunResult,
    TraceRunStatus,
)
from llm_sca_tooling.traces.scope_filter import derive_scope_filter
from llm_sca_tooling.traces.service import capture_trace

__all__ = [
    "CompressedTrace",
    "DivergencePoint",
    "RawTraceArtefact",
    "ScopeFilter",
    "StateDiff",
    "TraceEvent",
    "TraceRunContract",
    "TraceRunResult",
    "TraceRunStatus",
    "build_environment_snapshot",
    "capture_trace",
    "derive_scope_filter",
    "validate_command_allowlist",
]
