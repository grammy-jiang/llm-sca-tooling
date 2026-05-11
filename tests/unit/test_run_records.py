"""Tests for the async run-record writer."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.errors import ClosedRunError
from llm_sca_tooling.operations.run_records import RunRecordWriter


async def test_run_lifecycle(run_record_writer: RunRecordWriter) -> None:
    run_id = await run_record_writer.create_run("test-workflow", repos=[])
    assert run_id.startswith("run:")

    event_id = await run_record_writer.append_event(
        run_id, "gate", actor="agent", stage="verification"
    )
    assert event_id.startswith("evt:")

    await run_record_writer.close_run(run_id, status="complete")
    record = await run_record_writer.get_run(run_id)
    assert record is not None
    assert record.status == "complete"
    assert len(record.events) == 1


async def test_append_to_closed_run_raises_closed_run_error(
    run_record_writer: RunRecordWriter,
) -> None:
    run_id = await run_record_writer.create_run("wf", repos=[])
    await run_record_writer.close_run(run_id, status="complete")
    with pytest.raises(ClosedRunError):
        await run_record_writer.append_event(run_id, "gate", actor="agent", stage="v")


async def test_get_run_unknown_id(run_record_writer: RunRecordWriter) -> None:
    result = await run_record_writer.get_run("run:nonexistent")
    assert result is None


async def test_run_id_is_unique(run_record_writer: RunRecordWriter) -> None:
    ids = {await run_record_writer.create_run("wf", repos=[]) for _ in range(10)}
    assert len(ids) == 10


async def test_close_run_sets_status(run_record_writer: RunRecordWriter) -> None:
    run_id = await run_record_writer.create_run("wf", repos=[])
    await run_record_writer.close_run(run_id, status="failed")
    record = await run_record_writer.get_run(run_id)
    assert record is not None
    assert record.status == "failed"


async def test_run_files_written_to_disk(
    run_record_writer: RunRecordWriter, tmp_path: Path
) -> None:
    writer = RunRecordWriter(base_dir=tmp_path / "runs")
    run_id = await writer.create_run("wf", repos=[])
    run_dir = tmp_path / "runs" / run_id
    assert (run_dir / "run-record.json").exists()

    await writer.append_event(run_id, "gate", actor="agent", stage="v")
    assert (run_dir / "events.jsonl").exists()
