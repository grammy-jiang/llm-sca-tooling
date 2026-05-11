"""Tests for the session trace writer."""

from __future__ import annotations

from pathlib import Path

import orjson
import pytest

from llm_sca_tooling.telemetry.trace_writer import TraceWriter


@pytest.fixture()
def writer(tmp_path: Path) -> TraceWriter:
    return TraceWriter(session_id="sess-test", trace_dir=tmp_path / "traces")


def _read_events(trace_dir: Path, session_id: str) -> list[dict]:
    path = trace_dir / f"{session_id}.jsonl"
    return [
        orjson.loads(line) for line in path.read_bytes().splitlines() if line.strip()
    ]


def test_session_lifecycle_writes_events(writer: TraceWriter, tmp_path: Path) -> None:
    writer.session_start()
    writer.session_end()
    events = _read_events(tmp_path / "traces", "sess-test")
    types = [e["type"] for e in events]
    assert "session_start" in types
    assert "session_end" in types


def test_sequence_numbers_monotonically_increase(
    writer: TraceWriter, tmp_path: Path
) -> None:
    for _ in range(5):
        writer.emit("tool_call", actor="agent", stage="execution")
    events = _read_events(tmp_path / "traces", "sess-test")
    seqs = [e["seq"] for e in events]
    assert seqs == list(range(1, 6))


def test_emit_returns_event_id(writer: TraceWriter) -> None:
    event_id = writer.emit("plan_created", actor="agent", stage="planning")
    assert event_id.startswith("evt:")


def test_sensitive_fields_are_redacted(writer: TraceWriter, tmp_path: Path) -> None:
    writer.emit("tool_call", actor="agent", stage="execution", api_key="secret123")
    events = _read_events(tmp_path / "traces", "sess-test")
    assert events[0]["api_key"] == "***REDACTED***"


def test_verification_event_fields(writer: TraceWriter, tmp_path: Path) -> None:
    writer.verification_event("make verify", "pass", [])
    events = _read_events(tmp_path / "traces", "sess-test")
    assert events[0]["check_name"] == "make verify"
    assert events[0]["outcome"] == "pass"


def test_trace_dir_created_if_missing(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b" / "c"
    writer = TraceWriter(session_id="s", trace_dir=deep)
    writer.session_start()
    assert (deep / "s.jsonl").exists()
