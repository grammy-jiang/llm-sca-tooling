"""Helper process for Python trace capture."""

from __future__ import annotations

import inspect
import os
import runpy
import sys
import time
from pathlib import Path
from types import FrameType
from typing import Any

import orjson

from llm_sca_tooling.traces.models import ScopeFilter, TraceEvent, TraceEventType
from llm_sca_tooling.traces.redaction import (
    redacted_return_type_hash,
    redacted_type_hint,
)
from llm_sca_tooling.traces.scope_filter import event_is_in_scope


class _TraceWriter:
    def __init__(
        self,
        *,
        events_path: Path,
        working_dir: Path,
        scope_filter: ScopeFilter,
        max_bytes: int,
        trace_lines: bool,
    ) -> None:
        self.events_path = events_path
        self.working_dir = working_dir.resolve()
        self.scope_filter = scope_filter
        self.max_bytes = max_bytes
        self.trace_lines = trace_lines
        self.event_count = 0
        self.bytes_written = 0
        self.truncated = False
        self.truncation_reason: str | None = None
        self.exception_type: str | None = None
        self._frame_depth: dict[int, int] = {}
        self._frame_recorded: dict[int, bool] = {}
        self._fh = events_path.open("wb")

    def close(self) -> None:
        self._fh.close()

    def trace(self, frame: FrameType, event: str, arg: object) -> Any:
        if event not in {"call", "return", "exception", "line"}:
            return self.trace
        if event == "line" and not self.trace_lines:
            return self.trace
        module = str(frame.f_globals.get("__name__", ""))
        function = frame.f_code.co_name
        file_path = Path(frame.f_code.co_filename).resolve()
        rel_path = self._relative_path(file_path)
        frame_id = id(frame)
        if event == "call":
            parent_depth = (
                self._frame_depth.get(id(frame.f_back), -1) if frame.f_back else -1
            )
            depth = parent_depth + 1
            record = self._should_record(module, function, rel_path, depth)
            self._frame_depth[frame_id] = depth
            self._frame_recorded[frame_id] = record
            if record:
                self._write_event(
                    TraceEvent(
                        event_id=self._next_event_id(),
                        event_type=TraceEventType.CALL,
                        module=module,
                        function=function,
                        file_path=rel_path,
                        line_number=frame.f_lineno,
                        depth=depth,
                        arg_type_hints=self._arg_hints(frame),
                        ts_ns=time.time_ns(),
                    )
                )
            return self.trace
        record = self._frame_recorded.get(frame_id, False)
        depth = self._frame_depth.get(frame_id, 0)
        if record:
            if event == "return":
                self._write_event(
                    TraceEvent(
                        event_id=self._next_event_id(),
                        event_type=TraceEventType.RETURN,
                        module=module,
                        function=function,
                        file_path=rel_path,
                        line_number=frame.f_lineno,
                        depth=depth,
                        return_type_hash=redacted_return_type_hash(arg),
                        ts_ns=time.time_ns(),
                    )
                )
                self._frame_depth.pop(frame_id, None)
                self._frame_recorded.pop(frame_id, None)
            elif event == "exception":
                exc_type = arg[0].__name__ if isinstance(arg, tuple) and arg else None
                self.exception_type = exc_type or self.exception_type
                self._write_event(
                    TraceEvent(
                        event_id=self._next_event_id(),
                        event_type=TraceEventType.EXCEPTION,
                        module=module,
                        function=function,
                        file_path=rel_path,
                        line_number=frame.f_lineno,
                        depth=depth,
                        exception_type=exc_type,
                        exception_message_redacted=True,
                        ts_ns=time.time_ns(),
                    )
                )
            elif event == "line":
                self._write_event(
                    TraceEvent(
                        event_id=self._next_event_id(),
                        event_type=TraceEventType.LINE,
                        module=module,
                        function=function,
                        file_path=rel_path,
                        line_number=frame.f_lineno,
                        depth=depth,
                        ts_ns=time.time_ns(),
                    )
                )
        return self.trace

    def _should_record(
        self, module: str, function: str, rel_path: str, depth: int
    ) -> bool:
        if depth > self.scope_filter.max_call_depth:
            return False
        return event_is_in_scope(
            module=module,
            function=function,
            file_path=rel_path,
            scope_filter=self.scope_filter,
        )

    def _relative_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.working_dir).as_posix()
        except ValueError:
            if self.scope_filter.trace_stdlib or self.scope_filter.trace_third_party:
                return path.as_posix()
            return "__outside_scope__"

    def _arg_hints(self, frame: FrameType) -> dict[str, str]:
        try:
            args = inspect.getargvalues(frame)
        except Exception:
            return {}
        hints: dict[str, str] = {}
        kwonlyargs = getattr(args, "kwonlyargs", [])
        for name in [*args.args, *kwonlyargs]:
            if name in args.locals:
                hints[name] = redacted_type_hint(name, args.locals[name])
        if args.varargs and args.varargs in args.locals:
            hints[args.varargs] = redacted_type_hint(
                args.varargs, args.locals[args.varargs]
            )
        if args.keywords and args.keywords in args.locals:
            hints[args.keywords] = redacted_type_hint(
                args.keywords, args.locals[args.keywords]
            )
        return hints

    def _write_event(self, event: TraceEvent) -> None:
        if self.truncated:
            return
        payload = event.model_dump_json() + "\n"
        size = len(payload.encode("utf-8"))
        if self.bytes_written + size > self.max_bytes:
            self.truncated = True
            self.truncation_reason = "max_raw_trace_bytes_exceeded"
            return
        self._fh.write(payload.encode("utf-8"))
        self.bytes_written += size
        self.event_count += 1

    def _next_event_id(self) -> str:
        return f"te:{self.event_count + 1:08d}"


def main() -> int:
    contract_path = Path(sys.argv[1])
    events_path = Path(sys.argv[2])
    metadata_path = Path(sys.argv[3])
    payload = orjson.loads(contract_path.read_bytes())
    working_dir = Path(str(payload["working_dir"])).resolve()
    command = Path(str(payload["command"])).resolve()
    args = [str(item) for item in payload.get("args", [])]
    scope_filter = ScopeFilter.model_validate(payload["scope_filter"])
    writer = _TraceWriter(
        events_path=events_path,
        working_dir=working_dir,
        scope_filter=scope_filter,
        max_bytes=int(payload["max_raw_trace_bytes"]),
        trace_lines=bool(payload.get("trace_lines", False)),
    )
    exit_code = 0
    diagnostics: list[dict[str, object]] = []
    old_argv = sys.argv[:]
    old_cwd = Path.cwd()
    try:
        os.chdir(working_dir)
        sys.path.insert(0, str(working_dir))
        sys.argv = [str(command), *args]
        sys.settrace(writer.trace)
        try:
            runpy.run_path(str(command), run_name="__main__")
        except SystemExit as exc:
            code = exc.code
            exit_code = code if isinstance(code, int) else 1
        except BaseException as exc:
            writer.exception_type = exc.__class__.__name__
            exit_code = 1
    finally:
        sys.settrace(None)
        sys.argv = old_argv
        os.chdir(old_cwd)
        writer.close()
    metadata = {
        "event_count": writer.event_count,
        "truncated": writer.truncated,
        "truncation_reason": writer.truncation_reason,
        "exception_type": writer.exception_type,
        "exit_code": exit_code,
        "diagnostics": diagnostics,
    }
    metadata_path.write_bytes(orjson.dumps(metadata, option=orjson.OPT_SORT_KEYS))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
