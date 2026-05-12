"""NullTraceSummarizer — deterministic test double, no LLM calls."""

from __future__ import annotations

from llm_sca_tooling.traces.artefact_store import load_events
from llm_sca_tooling.traces.compression.interface import TraceSummarizerInterface
from llm_sca_tooling.traces.models import (
    CompressedTrace,
    RawTraceArtefact,
    ScopeFilter,
    TraceEvent,
)


class NullTraceSummarizer(TraceSummarizerInterface):
    model_id = "null"
    version = "phase16.v1"

    def summarize(
        self,
        raw_artefact: RawTraceArtefact,
        scope_filter: ScopeFilter,
        budget_tokens: int = 2000,
    ) -> CompressedTrace:
        raw_events = load_events(raw_artefact)
        # Take at most max_events from the raw artefact
        max_events = min(50, len(raw_events))
        relevant: list[TraceEvent] = []
        exceptions: list[TraceEvent] = []
        for row in raw_events[:max_events]:
            evt = TraceEvent.model_validate(row)
            if evt.event_type == "exception":
                exceptions.append(evt)
            else:
                relevant.append(evt)

        token_est = max_events * 20
        ratio = len(raw_events) / max(1, max_events)

        return CompressedTrace(
            trace_run_id=raw_artefact.trace_run_id,
            raw_artefact_id=raw_artefact.artefact_id,
            executed_path_summary=(
                f"null-mode: {len(raw_events)} raw events compressed to {max_events}"
            ),
            relevant_events=relevant[:50],
            exception_events=exceptions,
            compressed_token_estimate=token_est,
            compression_ratio=ratio,
            scope_coverage=1.0 if raw_events else 0.0,
            uncertainty_notes=(
                ["null_summarizer: no LLM inference applied"] if not raw_events else []
            ),
            summarizer_model=self.model_id,
            confidence="unknown",
        )
