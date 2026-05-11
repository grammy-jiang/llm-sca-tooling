"""Phase 11 patch review DryRUNMismatch trace divergence linkage."""

from __future__ import annotations

from llm_sca_tooling.traces.models import DivergencePoint


def link_mismatch_to_divergence(
    mismatch_diff_id: str,
    divergence_points: list[DivergencePoint],
) -> str | None:
    """Return the divergence point ref for a DryRUN mismatch, if available."""
    if not divergence_points:
        return None
    dp = divergence_points[0]
    return f"divergence:{dp.trace_run_id}/{dp.function_path}"
