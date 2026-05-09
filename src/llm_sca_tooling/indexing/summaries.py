"""Snapshot-keyed symbol summary cache plumbing."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from llm_sca_tooling.indexing.hashing import hash_text
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import DerivationType
from llm_sca_tooling.schemas.provenance import ArtifactRef, Provenance, SourceSpan
from llm_sca_tooling.storage.workspace import _now_ts


class SymbolSummaryRecord(StrictBaseModel):
    summary_id: str
    repo_id: str
    snapshot_id: str
    symbol_node_id: str
    symbol_path: str
    file_path: str
    span: SourceSpan | None = None
    file_hash: str
    summary_text: str
    confidence: float
    derivation: DerivationType
    generator_id: str
    source_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    created_ts: str
    invalidated_ts: str | None = None
    invalidation_reason: str | None = None
    provenance: Provenance


class SummaryCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def key(self, *, repo_id: str, snapshot_id: str, symbol_node_id: str, file_path: str, file_hash: str, generator_id: str = "stub", policy_hash: str = "default") -> str:
        return f"summary:{hash_text('|'.join([repo_id, snapshot_id, symbol_node_id, file_path, file_hash, generator_id, policy_hash]), length=32)}"

    def put(self, record: SymbolSummaryRecord) -> SymbolSummaryRecord:
        (self.root / f"{record.summary_id.replace(':', '_')}.json").write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return record

    def get_current(self, summary_id: str) -> SymbolSummaryRecord | None:
        path = self.root / f"{summary_id.replace(':', '_')}.json"
        if not path.exists():
            return None
        record = SymbolSummaryRecord.model_validate_json(path.read_text(encoding="utf-8"))
        return None if record.invalidated_ts else record

    def invalidate_for_files(self, file_paths: list[str], reason: str) -> int:
        count = 0
        for path in self.root.glob("summary_*.json"):
            record = SymbolSummaryRecord.model_validate_json(path.read_text(encoding="utf-8"))
            if record.file_path in file_paths and not record.invalidated_ts:
                record.invalidated_ts = _now_ts()
                record.invalidation_reason = reason
                path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
                count += 1
        return count
