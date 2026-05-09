from __future__ import annotations

import json

from llm_sca_tooling.telemetry.logging import get_logger
from llm_sca_tooling.telemetry.trace_writer import TraceWriter


def test_get_logger_does_not_duplicate_handlers() -> None:
    logger = get_logger("llm_sca_tooling.tests.telemetry")
    first_count = len(logger.handlers)
    logger = get_logger("llm_sca_tooling.tests.telemetry")
    assert len(logger.handlers) == first_count


def test_trace_writer_emits_sequence_and_redacts(tmp_path) -> None:
    writer = TraceWriter("session-1", tmp_path)
    writer.session_start()
    writer.tool_call("read", "read", "allow", token="secret")
    writer.session_end("complete")
    events = [
        json.loads(line)
        for line in (tmp_path / "session-1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [event["seq"] for event in events] == [1, 2, 3]
    assert events[1]["token"] == "[REDACTED]"
