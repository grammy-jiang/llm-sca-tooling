"""Python trace adapter using sys.settrace."""

from __future__ import annotations

import types
import uuid
from pathlib import Path

from llm_sca_tooling.traces.adapters.base import TraceAdapterBase
from llm_sca_tooling.traces.artefact_store import write_artefact
from llm_sca_tooling.traces.models import RawTraceArtefact, TraceEvent, TraceRunContract
from llm_sca_tooling.traces.scope_filter import is_in_scope


class PyTraceAdapter(TraceAdapterBase):
    adapter_id = "python"
    language = "python"

    async def run(
        self,
        contract: TraceRunContract,
        *,
        workspace_root: Path | None = None,
    ) -> tuple[RawTraceArtefact, bool]:
        trace_run_id = f"pytrace:{uuid.uuid4().hex[:8]}"
        events: list[TraceEvent] = []
        scope = contract.scope_filter
        max_events = contract.max_compressed_events * 10
        counter = [0]
        non_reproducing_flag = [True]

        def tracer(frame: types.FrameType, event: str, arg: object) -> object:
            if counter[0] >= max_events:
                return None
            module = frame.f_globals.get("__name__", "")
            file_path = frame.f_code.co_filename
            if not is_in_scope(module, file_path, scope):
                return tracer
            counter[0] += 1
            exc_type = None
            exc_msg_redacted = False
            if event == "exception" and isinstance(arg, tuple):
                exc_type = arg[0].__name__ if arg[0] else None
                exc_msg_redacted = True
                non_reproducing_flag[0] = False
            events.append(
                TraceEvent(
                    event_id=f"evt:{counter[0]}",
                    event_type=(
                        event if event in {"call", "return", "exception"} else "line"
                    ),
                    module=module,
                    function=frame.f_code.co_name,
                    file_path=file_path,
                    line_number=frame.f_lineno,
                    depth=(len(frame.f_back.f_code.co_name) if frame.f_back else 0),
                    exception_type=exc_type,
                    exception_message_redacted=exc_msg_redacted,
                    redaction_applied=True,
                )
            )
            return tracer

        script_path = Path(contract.command)
        if not script_path.exists():
            artefact = write_artefact(
                trace_run_id, [], workspace_root=workspace_root, language="python"
            )
            return artefact, True

        import sys

        old_trace = sys.gettrace()
        try:
            sys.settrace(tracer)  # type: ignore[arg-type]
            code = compile(script_path.read_text(), str(script_path), "exec")
            exec(  # noqa: S102  # nosec B102
                code, {"__name__": "__main__", "__file__": str(script_path)}
            )
        except SystemExit:
            pass
        except Exception:
            non_reproducing_flag[0] = False
        finally:
            sys.settrace(old_trace)

        artefact = write_artefact(
            trace_run_id,
            events,
            workspace_root=workspace_root,
            language="python",
            max_bytes=contract.max_raw_trace_bytes,
        )
        return artefact, non_reproducing_flag[0]
