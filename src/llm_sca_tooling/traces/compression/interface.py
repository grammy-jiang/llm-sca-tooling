"""Trace compression interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from llm_sca_tooling.traces.models import CompressedTrace, RawTraceArtefact, ScopeFilter


class TraceSummarizerInterface(ABC):
    model_id: str
    version: str

    @abstractmethod
    async def summarize(
        self,
        raw_artefact: RawTraceArtefact,
        scope_filter: ScopeFilter,
        budget_tokens: int,
    ) -> CompressedTrace:
        raise NotImplementedError
