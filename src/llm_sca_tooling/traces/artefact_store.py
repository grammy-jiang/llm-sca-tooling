"""Raw trace artefact store — JSONL writer with HC2 path compliance."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.traces.models import RawTraceArtefact, TraceEvent


def write_artefact(
    trace_run_id: str,
    events: list[TraceEvent],
    *,
    workspace_root: Path | None = None,
    language: str = "python",
    truncated: bool = False,
    truncation_reason: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,
) -> RawTraceArtefact:
    root = workspace_root or Path(".agent/eval/traces")
    root.mkdir(parents=True, exist_ok=True)
    artefact_id = f"trace:{uuid.uuid4().hex[:8]}"
    jsonl_path = root / f"{artefact_id}.jsonl"
    data = b"\n".join(orjson.dumps(e.model_dump(mode="json")) for e in events)
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated = True
        truncation_reason = "max_raw_trace_bytes_exceeded"
    jsonl_path.write_bytes(data)
    return RawTraceArtefact(
        artefact_id=artefact_id,
        trace_run_id=trace_run_id,
        language=language,
        adapter_version="phase16.v1",
        events_jsonl_path=str(jsonl_path),
        event_count=len(events),
        truncated=truncated,
        truncation_reason=truncation_reason,
        size_bytes=len(data),
    )


def load_events(artefact: RawTraceArtefact) -> list[dict[str, Any]]:
    path = Path(artefact.events_jsonl_path)
    if not path.exists():
        return []
    return [
        orjson.loads(line) for line in path.read_bytes().splitlines() if line.strip()
    ]
