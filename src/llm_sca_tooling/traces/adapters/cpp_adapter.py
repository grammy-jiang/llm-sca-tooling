"""C and C++ trace adapter placeholder."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.traces.adapters.base import AdapterCaptureResult, TraceAdapterBase
from llm_sca_tooling.traces.models import TraceRunContract, TraceRunStatus


class CppTraceAdapterPlaceholder(TraceAdapterBase):
    adapter_id = "cpp-probe-placeholder"
    supported_languages = ("c", "cpp")

    async def capture(
        self,
        *,
        trace_run_id: str,
        contract: TraceRunContract,
        artifact_root: Path,
    ) -> AdapterCaptureResult:
        return AdapterCaptureResult(
            status=TraceRunStatus.NOT_IMPLEMENTED,
            diagnostics=[
                {
                    "code": "cpp_trace_adapter_not_available",
                    "planned_mechanisms": ["asan", "ubsan", "rr", "gdb", "probes"],
                }
            ],
        )
