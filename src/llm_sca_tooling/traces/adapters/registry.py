"""Trace adapter registry."""

from __future__ import annotations

from llm_sca_tooling.traces.adapters.base import TraceAdapterBase
from llm_sca_tooling.traces.adapters.cpp_adapter import CppTraceAdapterPlaceholder
from llm_sca_tooling.traces.adapters.js_adapter import JSTraceAdapterPlaceholder
from llm_sca_tooling.traces.adapters.python_adapter import PyTraceAdapter


class TraceAdapterRegistry:
    def __init__(self, adapters: list[TraceAdapterBase] | None = None) -> None:
        self._adapters: dict[str, TraceAdapterBase] = {}
        for adapter in adapters or [
            PyTraceAdapter(),
            JSTraceAdapterPlaceholder(),
            CppTraceAdapterPlaceholder(),
        ]:
            for language in adapter.supported_languages:
                self.register(language, adapter)

    def register(self, language: str, adapter: TraceAdapterBase) -> None:
        self._adapters[language] = adapter

    def get(self, language: str) -> TraceAdapterBase:
        try:
            return self._adapters[language]
        except KeyError as exc:
            raise KeyError(f"trace language not registered: {language}") from exc

    def available_languages(self) -> list[str]:
        return sorted(self._adapters)
