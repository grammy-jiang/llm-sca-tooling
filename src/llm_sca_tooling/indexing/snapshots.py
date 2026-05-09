"""Snapshot ledger for incremental indexing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SnapshotLedger:
    """Tracks per-file content hashes for incremental indexing decisions."""

    snapshot_id: str
    _entries: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def record_file_snapshot(self, file_path: str | Path, sha256: str) -> None:
        """Record that a file was indexed with the given content hash."""
        self._entries[str(file_path)] = sha256

    def has_changed(self, file_path: str | Path, sha256: str) -> bool:
        """Return True if the file content differs from the last recorded hash."""
        key = str(file_path)
        return self._entries.get(key) != sha256

    def get_snapshot_manifest(self) -> dict[str, str]:
        """Return a copy of the full {file_path: sha256} ledger."""
        return dict(self._entries)

    def size(self) -> int:
        """Return the number of tracked files."""
        return len(self._entries)
