"""Trace compression and comparison helpers."""

from llm_sca_tooling.traces.compression.divergence import bind_divergence_points
from llm_sca_tooling.traces.compression.interface import TraceSummarizerInterface
from llm_sca_tooling.traces.compression.null_summarizer import NullTraceSummarizer
from llm_sca_tooling.traces.compression.state_diff import (
    compare_trace_events,
    load_trace_events,
)

__all__ = [
    "NullTraceSummarizer",
    "TraceSummarizerInterface",
    "bind_divergence_points",
    "compare_trace_events",
    "load_trace_events",
]
