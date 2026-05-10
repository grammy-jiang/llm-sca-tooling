"""JavaScript and TypeScript trace adapter placeholder."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.traces.adapters.base import AdapterCaptureResult, TraceAdapterBase
from llm_sca_tooling.traces.models import TraceRunContract, TraceRunStatus


class JSTraceAdapterPlaceholder(TraceAdapterBase):
    adapter_id = "node-inspector-placeholder"
    supported_languages = ("javascript", "typescript")

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
                    "code": "js_trace_adapter_not_available",
                    "planned_mechanism": "node --inspect / V8 inspector",
                }
            ],
        )
