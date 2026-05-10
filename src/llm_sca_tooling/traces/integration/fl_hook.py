"""Fault-localisation trace augmentation hook."""

from __future__ import annotations

from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    LocalisationResult,
    SignalType,
)
from llm_sca_tooling.traces.models import TraceRunResult


def augment_localisation_with_trace(
    result: LocalisationResult,
    trace_result: TraceRunResult,
    *,
    repo_id: str = "trace",
) -> LocalisationResult:
    existing_nodes = {candidate.node_id for candidate in result.ranked_files}
    additions: list[CandidateFile] = []
    for index, point in enumerate(trace_result.divergence_points, start=1):
        if not point.graph_node_id or point.graph_node_id in existing_nodes:
            continue
        additions.append(
            CandidateFile(
                candidate_id=f"trace:{trace_result.trace_run_id}:{index}",
                file_path=point.file_path or "unknown",
                repo_id=repo_id,
                node_id=point.graph_node_id,
                signals=[
                    CandidateSignal(
                        signal_type=SignalType.SBFL,
                        raw_score=0.85,
                        weight=1.0,
                        weighted_score=0.85,
                        evidence=f"trace divergence: {point.divergence_type.value}",
                        source_refs=[
                            point.pre_fix_event_ref or point.post_fix_event_ref or ""
                        ],
                        confidence=ConfidenceLevel.HEURISTIC,
                    )
                ],
                combined_score=0.85,
                confidence=ConfidenceLevel.HEURISTIC,
                evidence_summary="dynamic trace divergence",
            )
        )
        existing_nodes.add(point.graph_node_id)
    if not additions:
        return result
    return result.model_copy(
        update={
            "ranked_files": [*result.ranked_files, *additions],
            "diagnostics": [
                *result.diagnostics,
                {
                    "code": "trace_augmented",
                    "trace_run_id": trace_result.trace_run_id,
                    "added": len(additions),
                },
            ],
        }
    )
