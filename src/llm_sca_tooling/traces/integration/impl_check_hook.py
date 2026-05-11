"""Phase 14 Stage 6b implementation-check dynamic verdict hook."""

from __future__ import annotations

from llm_sca_tooling.impl_check.models import DynamicVerdictRecord
from llm_sca_tooling.traces.models import CompressedTrace, TraceRunResult


def make_dynamic_verdict_from_trace(
    clause_id: str,
    result: TraceRunResult,
    compressed: CompressedTrace | None,
) -> DynamicVerdictRecord:
    """Convert a trace result into a DynamicVerdictRecord for Stage 6b."""
    if result.status == "not_implemented":
        return DynamicVerdictRecord(
            clause_id=clause_id,
            stage="6b",
            available=False,
            verdict="unknown",
            confidence="unknown",
        )
    if result.non_reproducing:
        return DynamicVerdictRecord(
            clause_id=clause_id,
            stage="6b",
            trace_run_id=result.trace_run_id,
            compressed_trace_ref=result.compressed_trace_ref,
            available=True,
            verdict="unknown",
            confidence="unknown",
        )
    verdict = "unknown"
    if compressed and compressed.exception_events:
        verdict = "violated"
    elif compressed and compressed.relevant_events:
        verdict = "satisfied"
    return DynamicVerdictRecord(
        clause_id=clause_id,
        stage="6b",
        trace_run_id=result.trace_run_id,
        compressed_trace_ref=result.compressed_trace_ref,
        available=True,
        verdict=verdict,
        confidence="heuristic",
    )
