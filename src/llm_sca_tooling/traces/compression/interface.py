"""Trace summarizer interface — the mandatory LLM boundary for trace data."""

from __future__ import annotations

from abc import ABC, abstractmethod

from llm_sca_tooling.traces.models import (
    CompressedTrace,
    RawTraceArtefact,
    ScopeFilter,
)


class TraceSummarizerInterface(ABC):
    model_id: str
    version: str

    @abstractmethod
    def summarize(
        self,
        raw_artefact: RawTraceArtefact,
        scope_filter: ScopeFilter,
        budget_tokens: int,
    ) -> CompressedTrace:
        raise NotImplementedError
