"""Trace adapter registry."""

from __future__ import annotations

from llm_sca_tooling.traces.adapters.base import TraceAdapterBase
from llm_sca_tooling.traces.adapters.cpp_adapter import CppTraceAdapterPlaceholder
from llm_sca_tooling.traces.adapters.js_adapter import JSTraceAdapterPlaceholder
from llm_sca_tooling.traces.adapters.python_adapter import PyTraceAdapter


class TraceAdapterRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, TraceAdapterBase] = {}

    def register(self, language: str, adapter: TraceAdapterBase) -> None:
        self._registry[language] = adapter

    def get(self, language: str) -> TraceAdapterBase | None:
        return self._registry.get(language)

    def available_languages(self) -> list[str]:
        return list(self._registry)


def build_default_registry() -> TraceAdapterRegistry:
    registry = TraceAdapterRegistry()
    registry.register("python", PyTraceAdapter())
    registry.register("javascript", JSTraceAdapterPlaceholder())
    registry.register("typescript", JSTraceAdapterPlaceholder())
    registry.register("cpp", CppTraceAdapterPlaceholder())
    registry.register("c", CppTraceAdapterPlaceholder())
    return registry
