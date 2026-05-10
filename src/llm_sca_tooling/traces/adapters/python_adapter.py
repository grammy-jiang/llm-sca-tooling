"""Python sys.settrace adapter driven through an isolated helper process."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.storage.workspace import _now_ts
from llm_sca_tooling.traces.adapters.base import AdapterCaptureResult, TraceAdapterBase
from llm_sca_tooling.traces.artefact_store import trace_run_dir
from llm_sca_tooling.traces.models import (
    RawTraceArtefact,
    TraceLanguage,
    TraceRunContract,
    TraceRunStatus,
)
from llm_sca_tooling.traces.redaction import (
    environment_snapshot_hash,
    redaction_policy_hash,
)


class PyTraceAdapter(TraceAdapterBase):
    adapter_id = "python-sys-settrace"
    adapter_version = "python-sys-settrace/phase16"
    supported_languages = (TraceLanguage.PYTHON.value,)

    async def capture(
        self,
        *,
        trace_run_id: str,
        contract: TraceRunContract,
        artifact_root: Path,
    ) -> AdapterCaptureResult:
        if contract.scope_filter.is_empty:
            return AdapterCaptureResult(
                status=TraceRunStatus.SCOPE_EMPTY,
                diagnostics=[{"code": "scope_empty"}],
            )

        run_dir = trace_run_dir(artifact_root, trace_run_id)
        events_path = run_dir / "events.jsonl"
        metadata_path = run_dir / "runner_meta.json"
        contract_path = run_dir / "runner_contract.json"
        payload = {
            "command": contract.command,
            "args": contract.args,
            "working_dir": contract.working_dir,
            "scope_filter": contract.scope_filter.model_dump(mode="json"),
            "redaction_policy": contract.redaction_policy,
            "max_raw_trace_bytes": contract.max_raw_trace_bytes,
            "trace_lines": contract.trace_lines,
        }
        contract_path.write_bytes(orjson.dumps(payload, option=orjson.OPT_SORT_KEYS))
        start = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "llm_sca_tooling.traces.adapters.python_runner",
            str(contract_path),
            str(events_path),
            str(metadata_path),
            cwd=contract.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=contract.timeout_seconds
            )
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            wall_ms = int((time.monotonic() - start) * 1000)
            raw = self._raw_artefact(trace_run_id, contract, events_path, {}, wall_ms)
            return AdapterCaptureResult(
                status=TraceRunStatus.TIMEOUT,
                raw_artefact=raw,
                wall_ms=wall_ms,
                diagnostics=[{"code": "trace_timeout"}],
            )

        wall_ms = int((time.monotonic() - start) * 1000)
        meta = _read_meta(metadata_path)
        raw = self._raw_artefact(trace_run_id, contract, events_path, meta, wall_ms)
        diagnostics = list(meta.get("diagnostics", []))
        if stdout:
            diagnostics.append({"code": "runner_stdout", "size_bytes": len(stdout)})
        if stderr:
            diagnostics.append(
                {
                    "code": "runner_stderr",
                    "size_bytes": len(stderr),
                    "text_redacted": True,
                }
            )

        exit_code = int(meta.get("exit_code", proc.returncode or 0))
        reproduced_failure = exit_code != 0 or bool(meta.get("exception_type"))
        non_reproducing = contract.expected_failure and not reproduced_failure
        if non_reproducing:
            status = TraceRunStatus.NOT_REPRODUCING
        elif raw.truncated:
            status = TraceRunStatus.TRUNCATED
        elif exit_code != 0 and not contract.expected_failure:
            status = TraceRunStatus.FAILED
        else:
            status = TraceRunStatus.COMPLETED
        return AdapterCaptureResult(
            status=status,
            raw_artefact=raw,
            non_reproducing=non_reproducing,
            wall_ms=wall_ms,
            diagnostics=diagnostics,
        )

    def _raw_artefact(
        self,
        trace_run_id: str,
        contract: TraceRunContract,
        events_path: Path,
        meta: dict[str, Any],
        wall_ms: int,
    ) -> RawTraceArtefact:
        if not events_path.exists():
            events_path.write_text("", encoding="utf-8")
        return RawTraceArtefact(
            artefact_id=f"trace-raw:{trace_run_id}",
            trace_run_id=trace_run_id,
            language=contract.language,
            adapter_version=self.adapter_version,
            events_jsonl_path=str(events_path),
            event_count=int(meta.get("event_count", 0)),
            truncated=bool(meta.get("truncated", False)),
            truncation_reason=meta.get("truncation_reason"),
            size_bytes=events_path.stat().st_size,
            git_sha=str(contract.environment_snapshot.get("git_sha") or "") or None,
            environment_snapshot_hash=environment_snapshot_hash(
                contract.environment_snapshot
            ),
            redaction_policy_hash=redaction_policy_hash(contract.redaction_policy),
            created_ts=_now_ts(),
        )


def _read_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"event_count": 0, "diagnostics": [{"code": "runner_meta_missing"}]}
    payload = orjson.loads(path.read_bytes())
    if isinstance(payload, dict):
        return dict(payload)
    return {"event_count": 0, "diagnostics": [{"code": "runner_meta_invalid"}]}
