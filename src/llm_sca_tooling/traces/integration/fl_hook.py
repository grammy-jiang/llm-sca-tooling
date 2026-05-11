"""Phase 9 fault localisation integration hook."""

from __future__ import annotations

from llm_sca_tooling.traces.models import CompressedTrace


def augment_fl_with_trace(
    ranked_candidates: list[dict[str, object]],
    compressed_trace: CompressedTrace,
) -> list[dict[str, object]]:
    """Add trace-based suspects to ranked candidates without replacing static ones."""
    divergence_files = {
        dp.file_path
        for dp in compressed_trace.divergence_points
        if dp.file_path and dp.file_path != "unknown"
    }
    augmented = list(ranked_candidates)
    for file_path in divergence_files:
        if not any(c.get("file_path") == file_path for c in augmented):
            augmented.append(
                {
                    "file_path": file_path,
                    "score": 0.5,
                    "repo_id": "trace-derived",
                    "confidence": "trace",
                }
            )
    return augmented
