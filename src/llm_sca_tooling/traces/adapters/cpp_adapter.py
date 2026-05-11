"""C and C++ trace adapter."""

from __future__ import annotations

import shutil
from pathlib import Path

from llm_sca_tooling.storage.workspace import _now_ts
from llm_sca_tooling.traces.adapters.base import AdapterCaptureResult, TraceAdapterBase
from llm_sca_tooling.traces.models import (
    RawTraceArtefact,
    TraceRunContract,
    TraceRunStatus,
)
from llm_sca_tooling.traces.redaction import (
    environment_snapshot_hash,
    redaction_policy_hash,
)


def _trace_run_dir(artifact_root: Path, trace_run_id: str) -> Path:
    run_dir = artifact_root / trace_run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _cpp_tool_available() -> bool:
    return shutil.which("rr") is not None or shutil.which("gdb") is not None


class CppTraceAdapter(TraceAdapterBase):
    adapter_id = "cpp-probe/v1"
    adapter_version = "cpp-probe/v1"
    supported_languages = ("c", "cpp")

    async def capture(
        self,
        *,
        trace_run_id: str,
        contract: TraceRunContract,
        artifact_root: Path,
    ) -> AdapterCaptureResult:
        if not _cpp_tool_available():
            return AdapterCaptureResult(
                status=TraceRunStatus.NOT_IMPLEMENTED,
                diagnostics=[
                    {
                        "code": "cpp_trace_adapter_not_available",
                        "reason": "neither rr nor gdb found on PATH",
                        "planned_mechanisms": ["asan", "ubsan", "rr", "gdb", "probes"],
                    }
                ],
            )
        run_dir = _trace_run_dir(artifact_root, trace_run_id)
        events_path = run_dir / "events.jsonl"
        events_path.write_text("", encoding="utf-8")
        raw = RawTraceArtefact(
            artefact_id=f"trace-raw:{trace_run_id}",
            trace_run_id=trace_run_id,
            language=contract.language,
            adapter_version=self.adapter_version,
            events_jsonl_path=str(events_path),
            event_count=0,
            size_bytes=0,
            environment_snapshot_hash=environment_snapshot_hash(
                contract.environment_snapshot
            ),
            redaction_policy_hash=redaction_policy_hash(contract.redaction_policy),
            created_ts=_now_ts(),
        )
        return AdapterCaptureResult(
            status=TraceRunStatus.COMPLETED,
            raw_artefact=raw,
            diagnostics=[{"code": "cpp_stub_no_events"}],
        )


CppTraceAdapterPlaceholder = CppTraceAdapter
