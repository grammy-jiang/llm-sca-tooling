"""Ledger exporter — exports ledger records to a portable JSONL archive."""

from __future__ import annotations

import gzip
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["LedgerExporter", "ExportManifest"]

logger = get_logger(__name__)


class ExportManifest:
    def __init__(
        self,
        output_path: Path,
        record_count: int,
        date_from: str | None,
        date_to: str | None,
    ) -> None:
        self.output_path = output_path
        self.record_count = record_count
        self.date_from = date_from
        self.date_to = date_to
        self.ts = datetime.now(UTC).isoformat()


class LedgerExporter:
    """Export ledger records to a compressed JSONL archive.

    Args:
        records: Iterable of record dicts from the operational store.
    """

    # Default fields excluded from export (HC1/HC6 compliance)
    _EXCLUDED_FIELDS = {"raw_trace", "source_content", "credential"}

    def export(
        self,
        records: list[dict[str, Any]],
        output_path: str | Path,
        date_from: date | None = None,
        date_to: date | None = None,
        repo_filter: str | None = None,
        workflow_filter: str | None = None,
        incident_id: str | None = None,
        compress: bool = True,
    ) -> ExportManifest:
        """Write *records* to *output_path* as (optionally compressed) JSONL.

        Applies date range, repo, workflow, and incident filters.
        Sensitive fields are stripped before writing.
        """
        filtered = self._filter(
            records,
            date_from=date_from,
            date_to=date_to,
            repo_filter=repo_filter,
            workflow_filter=workflow_filter,
            incident_id=incident_id,
        )
        cleaned = [self._strip_sensitive(r) for r in filtered]
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        if compress:
            with gzip.open(out, "wb") as fh:
                for record in cleaned:
                    fh.write(orjson.dumps(record) + b"\n")
        else:
            with out.open("wb") as fh:
                for record in cleaned:
                    fh.write(orjson.dumps(record) + b"\n")

        manifest = ExportManifest(
            output_path=out,
            record_count=len(cleaned),
            date_from=date_from.isoformat() if date_from else None,
            date_to=date_to.isoformat() if date_to else None,
        )
        logger.info("ledger_export: %d records -> %s", manifest.record_count, out)
        return manifest

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _filter(
        self,
        records: list[dict[str, Any]],
        date_from: date | None,
        date_to: date | None,
        repo_filter: str | None,
        workflow_filter: str | None,
        incident_id: str | None,
    ) -> list[dict[str, Any]]:
        result = []
        for r in records:
            if date_from or date_to:
                ts_str = r.get("ts") or r.get("created_at") or ""
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str).date()
                        if date_from and ts < date_from:
                            continue
                        if date_to and ts > date_to:
                            continue
                    except ValueError:
                        pass
            if repo_filter and r.get("repo_id") != repo_filter:
                continue
            if workflow_filter and r.get("workflow") != workflow_filter:
                continue
            if incident_id and r.get("incident_id") != incident_id:
                continue
            result.append(r)
        return result

    def _strip_sensitive(self, record: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in record.items() if k not in self._EXCLUDED_FIELDS}
