"""Stage 6b: Dynamic verdict hook (dormant in Phase 14)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from llm_sca_tooling.traces.models import TraceRunResult
from llm_sca_tooling.workflows.impl_check.models import (
    CheckabilityValue,
    Clause,
    ConfidenceLevel,
    DynamicVerdictRecord,
    VerdictValue,
)

_FAILURE_DIVERGENCE_TYPES = {
    "exception_raised_vs_not",
    "missing_call",
    "new_call",
    "branch_taken_vs_not_taken",
}


def _derive_verdict_from_trace(
    trace_result: TraceRunResult, clause: Clause
) -> VerdictValue:
    """Derive a clause verdict from a trace run result.

    Returns VIOLATED when divergence points indicate a failure-class divergence
    for DYNAMIC or HYBRID clauses, SATISFIED when trace is clean, UNKNOWN otherwise.
    """
    if clause.checkability not in {
        CheckabilityValue.DYNAMIC,
        CheckabilityValue.HYBRID,
    }:
        return VerdictValue.UNKNOWN
    if not trace_result.divergence_points:
        return VerdictValue.SATISFIED
    for point in trace_result.divergence_points:
        if point.divergence_type.value in _FAILURE_DIVERGENCE_TYPES:
            return VerdictValue.VIOLATED
    return VerdictValue.SATISFIED


def run_dynamic_verdict_hook(
    clause: Clause,
    trace_capture_fn: Callable[[Clause], Any] | None = None,
) -> DynamicVerdictRecord:
    """Stage 6b dynamic hook. Uses Phase 16 trace output when provided."""
    if trace_capture_fn is None or clause.checkability not in {
        CheckabilityValue.DYNAMIC,
        CheckabilityValue.HYBRID,
    }:
        return DynamicVerdictRecord(
            clause_id=clause.clause_id,
            stage="6b",
            verdict=VerdictValue.UNKNOWN,
            available=False,
        )
    captured = trace_capture_fn(clause)
    if captured is None:
        return DynamicVerdictRecord(
            clause_id=clause.clause_id,
            stage="6b",
            verdict=VerdictValue.UNKNOWN,
            available=False,
        )
    trace_result = _trace_result(captured)
    if trace_result is None:
        return DynamicVerdictRecord(
            clause_id=clause.clause_id,
            stage="6b",
            verdict=VerdictValue.UNKNOWN,
            available=False,
        )
    verdict = _derive_verdict_from_trace(trace_result, clause)
    return DynamicVerdictRecord(
        clause_id=clause.clause_id,
        stage="6b",
        trace_run_id=trace_result.trace_run_id,
        compressed_trace_ref=trace_result.compressed_trace_ref,
        verdict=verdict,
        divergence_points=[
            point.graph_node_id or point.function_path
            for point in trace_result.divergence_points
        ],
        confidence=ConfidenceLevel.HEURISTIC,
        available=True,
    )


def _trace_result(value: Any) -> TraceRunResult | None:
    if isinstance(value, TraceRunResult):
        return value
    if isinstance(value, dict):
        payload = value.get("result", value)
        if isinstance(payload, dict):
            return TraceRunResult.model_validate(payload)
    return None
