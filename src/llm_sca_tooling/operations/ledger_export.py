"""Operational ledger export helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from pydantic import Field

from llm_sca_tooling.privacy.redaction import redact_for_export
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


class _OperationalStore(Protocol):
    def query_operational_records(
        self,
        repo_id: str | None = None,
        run_id: str | None = None,
        kind: str | None = None,
        *,
        time_range: tuple[str, str] | None = None,
    ) -> list[object]: ...

    def query_incidents(
        self, repo_id: str | None = None, **kwargs: object
    ) -> list[object]: ...


class LedgerExportResult(StrictBaseModel):
    destination: str = Field(min_length=1)
    record_count: int
    incident_count: int
    redacted: bool


class LedgerExportService:
    def __init__(self, store: _OperationalStore) -> None:
        self.store = store

    def export_operational_ledger(
        self,
        destination: str | Path,
        *,
        repo_id: str | None = None,
        run_id: str | None = None,
        redacted: bool = True,
    ) -> LedgerExportResult:
        records = [
            _model_to_json(record)
            for record in self.store.query_operational_records(
                repo_id=repo_id, run_id=run_id
            )
        ]
        incidents = [
            _model_to_json(incident)
            for incident in self.store.query_incidents(repo_id=repo_id)
        ]
        payload: JsonObject = {
            "operational_records": records,
            "incidents": incidents,
        }
        if redacted:
            payload = redact_for_export(payload)  # type: ignore[assignment]
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return LedgerExportResult(
            destination=str(path),
            record_count=len(records),
            incident_count=len(incidents),
            redacted=redacted,
        )


def _model_to_json(value: object) -> JsonObject:
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        data = dump(mode="json")
        return data if isinstance(data, dict) else {"value": data}
    return value if isinstance(value, dict) else {"value": value}
