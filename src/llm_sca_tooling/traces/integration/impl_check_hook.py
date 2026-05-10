"""Implementation-check dynamic verdict payload mapping."""

from __future__ import annotations

from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.traces.models import TraceRunResult, TraceRunStatus


def dynamic_verdict_payload_from_trace(trace_result: TraceRunResult) -> JsonObject:
    """Return a workflow-neutral payload for Phase 14 Stage 6b."""
    return {
        "trace_run_id": trace_result.trace_run_id,
        "compressed_trace_ref": trace_result.compressed_trace_ref,
        "verdict": "unknown",
        "available": trace_result.status
        in {
            TraceRunStatus.COMPLETED,
            TraceRunStatus.TRUNCATED,
            TraceRunStatus.NOT_REPRODUCING,
        },
        "non_reproducing": trace_result.non_reproducing,
        "divergence_points": [
            point.graph_node_id or point.function_path
            for point in trace_result.divergence_points
        ],
    }
