"""Trace adapter implementations."""

from llm_sca_tooling.traces.adapters.base import AdapterCaptureResult, TraceAdapterBase
from llm_sca_tooling.traces.adapters.cpp_adapter import CppTraceAdapterPlaceholder
from llm_sca_tooling.traces.adapters.js_adapter import JSTraceAdapterPlaceholder
from llm_sca_tooling.traces.adapters.python_adapter import PyTraceAdapter
from llm_sca_tooling.traces.adapters.registry import TraceAdapterRegistry

__all__ = [
    "AdapterCaptureResult",
    "CppTraceAdapterPlaceholder",
    "JSTraceAdapterPlaceholder",
    "PyTraceAdapter",
    "TraceAdapterBase",
    "TraceAdapterRegistry",
]
