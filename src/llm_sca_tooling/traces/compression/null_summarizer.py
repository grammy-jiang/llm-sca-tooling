"""Deterministic trace summarizer used as the Phase 16 LLM boundary test double."""

from __future__ import annotations

from collections import OrderedDict

from llm_sca_tooling.traces.compression.interface import TraceSummarizerInterface
from llm_sca_tooling.traces.compression.state_diff import load_trace_events
from llm_sca_tooling.traces.models import (
    CompressedTrace,
    RawTraceArtefact,
    ScopeFilter,
    TraceConfidence,
    TraceEvent,
    TraceEventType,
)


class NullTraceSummarizer(TraceSummarizerInterface):
    model_id = "null"
    version = "phase16-null"

    async def summarize(
        self,
        raw_artefact: RawTraceArtefact,
        scope_filter: ScopeFilter,
        budget_tokens: int,
    ) -> CompressedTrace:
        events = load_trace_events(raw_artefact.events_jsonl_path)
        exception_events = [
            event for event in events if event.event_type is TraceEventType.EXCEPTION
        ][:50]
        relevant = _bounded_events(exception_events, events, limit=50)
        executed = list(
            OrderedDict.fromkeys(
                event.function_path for event in events if event.function_path
            )
        )
        token_estimate = min(
            budget_tokens,
            sum(max(1, len(event.model_dump_json()) // 4) for event in relevant),
        )
        compression_ratio = (
            raw_artefact.event_count / max(1, len(relevant))
            if raw_artefact.event_count
            else 1.0
        )
        notes = []
        if raw_artefact.truncated:
            notes.append("raw_trace_truncated")
        return CompressedTrace(
            trace_run_id=raw_artefact.trace_run_id,
            raw_artefact_id=raw_artefact.artefact_id,
            executed_path_summary=executed[:50],
            relevant_events=relevant,
            state_diffs=[],
            divergence_points=[],
            exception_events=exception_events,
            compressed_token_estimate=token_estimate,
            compression_ratio=compression_ratio,
            scope_coverage={
                "included_files": scope_filter.include_files,
                "included_modules": scope_filter.include_modules,
                "event_count": raw_artefact.event_count,
            },
            uncertainty_notes=notes,
            summarizer_model=self.model_id,
            confidence=TraceConfidence.UNKNOWN,
        )


def _bounded_events(
    exception_events: list[TraceEvent],
    all_events: list[TraceEvent],
    *,
    limit: int,
) -> list[TraceEvent]:
    selected: OrderedDict[str, TraceEvent] = OrderedDict()
    for event in [*exception_events, *all_events]:
        if event.event_id not in selected:
            selected[event.event_id] = event
        if len(selected) >= limit:
            break
    return list(selected.values())
