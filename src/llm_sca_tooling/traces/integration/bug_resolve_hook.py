"""Phase 13 bug-resolve gate runner trace hook."""

from __future__ import annotations

from llm_sca_tooling.traces.models import (
    CompressedTrace,
    TraceRunResult,
)


def apply_trace_to_gate_runner(
    result: TraceRunResult,
    compressed: CompressedTrace | None,
) -> dict[str, object]:
    """Return gate runner augmentation from trace evidence."""
    if result.status == "not_implemented" or result.non_reproducing:
        return {"trace_available": False, "divergence_points": []}
    return {
        "trace_available": True,
        "divergence_points": [
            dp.model_dump(mode="json") for dp in result.divergence_points
        ],
        "exception_count": len(compressed.exception_events) if compressed else 0,
    }
