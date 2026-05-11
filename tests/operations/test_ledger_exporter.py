"""Tests for LedgerExporter."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from llm_sca_tooling.operations.ledger_exporter import LedgerExporter


def test_export_empty_ledger(tmp_path: Path) -> None:
    out = tmp_path / "export.jsonl.gz"
    exporter = LedgerExporter()
    manifest = exporter.export(records=[], output_path=str(out))
    assert manifest.record_count == 0
    assert out.exists()


def test_export_creates_compressed_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "export.jsonl.gz"
    records = [
        {
            "event_id": "e1",
            "session_id": "s1",
            "ts": "2025-01-01T00:00:00Z",
            "type": "test",
        },
        {
            "event_id": "e2",
            "session_id": "s1",
            "ts": "2025-01-01T00:00:01Z",
            "type": "test",
        },
    ]
    exporter = LedgerExporter()
    manifest = exporter.export(records=records, output_path=str(out))
    assert manifest.record_count == 2
    with gzip.open(out) as fh:
        lines = fh.read().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event_id"] == "e1"


def test_export_uncompressed(tmp_path: Path) -> None:
    out = tmp_path / "export.jsonl"
    exporter = LedgerExporter()
    manifest = exporter.export(records=[{"x": 1}], output_path=str(out), compress=False)
    assert manifest.record_count == 1
    lines = out.read_bytes().splitlines()
    assert len(lines) == 1


def test_export_sensitive_fields_stripped(tmp_path: Path) -> None:
    out = tmp_path / "export.jsonl.gz"
    records = [{"event_id": "e1", "raw_trace": "secret", "data": "ok"}]
    exporter = LedgerExporter()
    exporter.export(records=records, output_path=str(out))
    with gzip.open(out) as fh:
        data = json.loads(fh.readline())
    assert "raw_trace" not in data
