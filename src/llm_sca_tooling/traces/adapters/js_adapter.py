"""JavaScript and TypeScript trace adapter."""

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


class JSTraceAdapter(TraceAdapterBase):
    adapter_id = "node-inspector/v1"
    adapter_version = "node-inspector/v1"
    supported_languages = ("javascript", "typescript")

    async def capture(
        self,
        *,
        trace_run_id: str,
        contract: TraceRunContract,
        artifact_root: Path,
    ) -> AdapterCaptureResult:
        if shutil.which("node") is None:
            return AdapterCaptureResult(
                status=TraceRunStatus.NOT_IMPLEMENTED,
                diagnostics=[
                    {
                        "code": "js_trace_adapter_not_available",
                        "reason": "node binary not found on PATH",
                        "planned_mechanism": "node --inspect / V8 inspector",
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
            diagnostics=[{"code": "js_stub_no_events"}],
        )


JSTraceAdapterPlaceholder = JSTraceAdapter
