"""Symbol summary cache — keyed by repo, symbol, snapshot, and span hash.

Phase 3 implements the cache plumbing.  Summary generation is a stub
(a deterministic placeholder is returned) until Phase 13+ activates
the real LLM-based generator.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["SummaryRecord", "SummaryCache"]

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class SummaryRecord:
    summary_id: str
    repo_id: str
    snapshot_id: str
    symbol_node_id: str
    symbol_path: str
    file_path: str
    summary_text: str
    confidence: float
    generator_id: str
    created_ts: str
    invalidated_ts: str | None = None
    invalidation_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.invalidated_ts is None


class SummaryCache:
    """In-process summary cache keyed by snapshot + symbol + span hash.

    Phase 3 stores records in memory.  Phase 13 replaces this with
    a persistent store and a real LLM generator.
    """

    def __init__(self) -> None:
        self._records: dict[str, SummaryRecord] = {}

    def _make_key(
        self,
        repo_id: str,
        symbol_node_id: str,
        snapshot_id: str,
        file_hash: str,
    ) -> str:
        raw = f"{repo_id}|{symbol_node_id}|{snapshot_id}|{file_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def get(
        self,
        repo_id: str,
        symbol_node_id: str,
        snapshot_id: str,
        file_hash: str,
    ) -> SummaryRecord | None:
        key = self._make_key(repo_id, symbol_node_id, snapshot_id, file_hash)
        record = self._records.get(key)
        return record if (record and record.is_valid) else None

    def put(
        self,
        repo_id: str,
        symbol_node_id: str,
        symbol_path: str,
        file_path: str,
        snapshot_id: str,
        file_hash: str,
        summary_text: str,
        *,
        confidence: float = 0.0,
        generator_id: str = "stub",
    ) -> SummaryRecord:
        key = self._make_key(repo_id, symbol_node_id, snapshot_id, file_hash)
        summary_id = f"sum:{key}"
        record = SummaryRecord(
            summary_id=summary_id,
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            symbol_node_id=symbol_node_id,
            symbol_path=symbol_path,
            file_path=file_path,
            summary_text=summary_text,
            confidence=confidence,
            generator_id=generator_id,
            created_ts=_now(),
        )
        self._records[key] = record
        return record

    def invalidate_for_file(self, repo_id: str, file_path: str) -> int:
        """Invalidate all summaries associated with *file_path*.

        Returns the count of invalidated records.
        """
        now = _now()
        count = 0
        for record in self._records.values():
            if (
                record.repo_id == repo_id
                and record.file_path == file_path
                and record.is_valid
            ):
                record.invalidated_ts = now
                record.invalidation_reason = f"file {file_path} changed"
                count += 1
        return count
