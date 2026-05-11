"""C and C++ trace adapter using rr, gdb, or sanitizer environment."""

from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.storage.workspace import _now_ts
from llm_sca_tooling.traces.adapters.base import AdapterCaptureResult, TraceAdapterBase
from llm_sca_tooling.traces.artefact_store import trace_run_dir
from llm_sca_tooling.traces.models import (
    RawTraceArtefact,
    TraceRunContract,
    TraceRunStatus,
)
from llm_sca_tooling.traces.redaction import (
    environment_snapshot_hash,
    redaction_policy_hash,
)


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

        rr_bin = shutil.which("rr")
        if rr_bin:
            return await self._capture_with_rr(
                trace_run_id, contract, artifact_root, rr_bin
            )

        gdb_bin = shutil.which("gdb")
        if gdb_bin:
            return await self._capture_with_gdb(
                trace_run_id, contract, artifact_root, gdb_bin
            )

        # Should not reach here due to _cpp_tool_available() check above
        return AdapterCaptureResult(
            status=TraceRunStatus.NOT_IMPLEMENTED,
            diagnostics=[{"code": "cpp_trace_adapter_not_available"}],
        )

    async def _capture_with_rr(
        self,
        trace_run_id: str,
        contract: TraceRunContract,
        artifact_root: Path,
        rr_bin: str,
    ) -> AdapterCaptureResult:
        run_dir = trace_run_dir(artifact_root, trace_run_id)
        events_path = run_dir / "events.jsonl"
        record_dir = run_dir / "rr_trace"
        cmd_parts = contract.command.split()
        cmd = (
            [rr_bin, "record", "-o", str(record_dir), "--"] + cmd_parts + contract.args
        )
        start = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
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
            raw = self._raw_artefact(
                trace_run_id, contract, events_path, {}, wall_ms, "rr"
            )
            return AdapterCaptureResult(
                status=TraceRunStatus.TIMEOUT,
                raw_artefact=raw,
                wall_ms=wall_ms,
                diagnostics=[{"code": "trace_timeout", "mechanism": "rr"}],
            )

        wall_ms = int((time.monotonic() - start) * 1000)
        exit_code = proc.returncode or 0
        # Parse rr output lines into trace events
        events = _parse_rr_output(stdout or b"", stderr or b"", contract)
        _write_events_jsonl(events_path, events)
        meta = {
            "event_count": len(events),
            "exit_code": exit_code,
            "diagnostics": [{"code": "mechanism", "value": "rr"}],
        }
        raw = self._raw_artefact(
            trace_run_id, contract, events_path, meta, wall_ms, "rr"
        )
        status = TraceRunStatus.COMPLETED if exit_code == 0 else TraceRunStatus.FAILED
        return AdapterCaptureResult(
            status=status,
            raw_artefact=raw,
            wall_ms=wall_ms,
            diagnostics=[{"code": "mechanism", "value": "rr"}],
        )

    async def _capture_with_gdb(
        self,
        trace_run_id: str,
        contract: TraceRunContract,
        artifact_root: Path,
        gdb_bin: str,
    ) -> AdapterCaptureResult:
        run_dir = trace_run_dir(artifact_root, trace_run_id)
        events_path = run_dir / "events.jsonl"
        gdb_script_path = run_dir / "gdb_batch.gdb"

        scope_modules = list(contract.scope_filter.include_modules or [])
        scope_fns = list(contract.scope_filter.include_functions or [])
        bp_targets = scope_fns[:20] if scope_fns else scope_modules[:10]
        bp_lines = "\n".join(f"break {t}" for t in bp_targets) if bp_targets else ""
        gdb_script_path.write_text(
            "set pagination off\nset confirm off\n" + bp_lines + "\nrun\nbt\nquit\n",
            encoding="utf-8",
        )

        cmd_parts = contract.command.split()
        cmd = (
            [gdb_bin, "-batch", "-x", str(gdb_script_path), "--args"]
            + cmd_parts
            + contract.args
        )
        start = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
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
            raw = self._raw_artefact(
                trace_run_id, contract, events_path, {}, wall_ms, "gdb"
            )
            return AdapterCaptureResult(
                status=TraceRunStatus.TIMEOUT,
                raw_artefact=raw,
                wall_ms=wall_ms,
                diagnostics=[{"code": "trace_timeout", "mechanism": "gdb"}],
            )

        wall_ms = int((time.monotonic() - start) * 1000)
        exit_code = proc.returncode or 0
        events = _parse_gdb_output(stdout or b"", contract)
        _write_events_jsonl(events_path, events)
        meta = {
            "event_count": len(events),
            "exit_code": exit_code,
            "diagnostics": [{"code": "mechanism", "value": "gdb"}],
        }
        raw = self._raw_artefact(
            trace_run_id, contract, events_path, meta, wall_ms, "gdb"
        )
        status = TraceRunStatus.COMPLETED if exit_code == 0 else TraceRunStatus.FAILED
        return AdapterCaptureResult(
            status=status,
            raw_artefact=raw,
            wall_ms=wall_ms,
            diagnostics=[{"code": "mechanism", "value": "gdb"}],
        )

    def _raw_artefact(
        self,
        trace_run_id: str,
        contract: TraceRunContract,
        events_path: Path,
        meta: dict[str, Any],
        wall_ms: int,
        mechanism: str,
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


def _parse_rr_output(
    stdout: bytes, stderr: bytes, contract: TraceRunContract
) -> list[dict[str, Any]]:
    """Parse rr record output into minimal trace events."""
    events: list[dict[str, Any]] = []
    combined = (stdout + stderr).decode(errors="replace")
    ts = 0
    for line in combined.splitlines():
        line = line.strip()
        if not line:
            continue
        # rr outputs function call info in the format: "fn(args)" or stack frames
        if line.startswith("#") and " in " in line:
            # GDB-style backtrace from rr: "#0  func_name (args) at file.c:42"
            parts = line.split()
            fn_name = parts[2] if len(parts) > 2 else "<unknown>"
            events.append(
                {
                    "event_id": f"trace-event:cpp-{len(events)}",
                    "event_type": "call",
                    "module": "",
                    "function": fn_name,
                    "file_path": "",
                    "line_number": 0,
                    "depth": int(parts[0].lstrip("#")) if parts else 0,
                    "arg_type_hints": {},
                    "return_type_hash": None,
                    "exception_type": None,
                    "exception_message_redacted": True,
                    "ts_ns": ts,
                    "redaction_applied": True,
                }
            )
            ts += 1000
    return events


def _parse_gdb_output(
    stdout: bytes, contract: TraceRunContract
) -> list[dict[str, Any]]:
    """Parse gdb -batch output into trace events."""
    events: list[dict[str, Any]] = []
    text = stdout.decode(errors="replace")
    ts = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Breakpoint hits: "Breakpoint N, function_name (args) at file.c:42"
        if line.startswith("Breakpoint"):
            parts = line.split(",", 2)
            fn_part = parts[1].strip() if len(parts) > 1 else "<unknown>"
            fn_name = fn_part.split("(")[0].strip()
            events.append(
                {
                    "event_id": f"trace-event:cpp-{len(events)}",
                    "event_type": "call",
                    "module": "",
                    "function": fn_name,
                    "file_path": "",
                    "line_number": 0,
                    "depth": 0,
                    "arg_type_hints": {},
                    "return_type_hash": None,
                    "exception_type": None,
                    "exception_message_redacted": True,
                    "ts_ns": ts,
                    "redaction_applied": True,
                }
            )
            ts += 1000
        # Stack frames in bt: "#N  function_name (args) at file.c:42"
        elif line.startswith("#"):
            parts = line.split()
            fn_name = parts[2] if len(parts) > 2 else "<unknown>"
            try:
                depth = int(parts[0].lstrip("#"))
            except (ValueError, IndexError):
                depth = 0
            events.append(
                {
                    "event_id": f"trace-event:cpp-{len(events)}",
                    "event_type": "call",
                    "module": "",
                    "function": fn_name,
                    "file_path": "",
                    "line_number": 0,
                    "depth": depth,
                    "arg_type_hints": {},
                    "return_type_hash": None,
                    "exception_type": None,
                    "exception_message_redacted": True,
                    "ts_ns": ts,
                    "redaction_applied": True,
                }
            )
            ts += 1000
    return events


def _write_events_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.write_bytes(
        b"\n".join(orjson.dumps(e) for e in events) + (b"\n" if events else b"")
    )


CppTraceAdapterPlaceholder = CppTraceAdapter
