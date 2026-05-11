"""C/C++ trace adapter using valgrind/rr/gdb subprocess tracing."""

from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from llm_sca_tooling.traces.adapters.base import TraceAdapterBase
from llm_sca_tooling.traces.artefact_store import write_artefact
from llm_sca_tooling.traces.models import RawTraceArtefact, TraceEvent, TraceRunContract


def _parse_callgrind(content: str) -> list[dict[str, object]]:
    """Extract function call events from callgrind output."""
    events = []
    counter = 0
    fn_re = re.compile(r"^fn=(.+)$")
    fl_re = re.compile(r"^fl=(.+)$")
    current_fn = ""
    current_file = ""
    for line in content.splitlines():
        m = fn_re.match(line)
        if m:
            current_fn = m.group(1)
        m2 = fl_re.match(line)
        if m2:
            current_file = m2.group(1)
        if line and line[0].isdigit() and current_fn:
            counter += 1
            parts = line.split()
            lineno = int(parts[0]) if parts else 0
            events.append(
                {
                    "event_id": f"cppc:{counter}",
                    "event_type": "call",
                    "module": current_file or "unknown",
                    "function": current_fn,
                    "file_path": current_file or "unknown",
                    "line_number": lineno,
                    "depth": 0,
                    "arg_type_hints": [],
                    "return_type_hash": None,
                    "exception_type": None,
                    "exception_message_redacted": False,
                    "ts_ns": 0,
                    "redaction_applied": True,
                }
            )
    return events


class CppTraceAdapterPlaceholder(TraceAdapterBase):
    """C/C++ trace adapter using valgrind callgrind instrumentation."""

    adapter_id = "cpp"
    language = "cpp"

    async def run(
        self,
        contract: TraceRunContract,
        *,
        workspace_root: Path | None = None,
    ) -> tuple[RawTraceArtefact, bool]:
        trace_run_id = f"cpptrace:{uuid.uuid4().hex[:8]}"

        valgrind_bin = shutil.which("valgrind")
        executable = Path(contract.command)
        if not valgrind_bin or not executable.exists():
            artefact = write_artefact(
                trace_run_id, [], workspace_root=workspace_root, language="cpp"
            )
            return artefact, True

        non_reproducing = True
        events: list[TraceEvent] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "callgrind.out"
            cmd = [
                valgrind_bin,
                "--tool=callgrind",
                f"--callgrind-out-file={out_file}",
                "--quiet",
                str(executable),
                *contract.args,
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=contract.working_dir,
                    env=contract.environment_snapshot or None,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(
                    proc.communicate(), timeout=float(contract.timeout_seconds)
                )
                non_reproducing = proc.returncode == 0
                if out_file.exists():
                    raw_events = _parse_callgrind(out_file.read_text())
                    scope = contract.scope_filter
                    max_events = contract.max_compressed_events * 10
                    for item in raw_events[:max_events]:
                        fn = str(item.get("function", ""))
                        if scope.include_functions and not any(
                            fn.startswith(f) for f in scope.include_functions
                        ):
                            continue
                        events.append(TraceEvent(**item))
            except TimeoutError:
                non_reproducing = False
            except Exception:
                non_reproducing = False

        artefact = write_artefact(
            trace_run_id,
            events,
            workspace_root=workspace_root,
            language="cpp",
            max_bytes=contract.max_raw_trace_bytes,
        )
        return artefact, non_reproducing
