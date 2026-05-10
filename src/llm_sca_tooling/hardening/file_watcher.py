"""Optional file watcher service with deterministic fallback."""

from __future__ import annotations

from pathlib import Path


class FileWatcherService:
    def __init__(self, *, debounce_seconds: float = 2.0) -> None:
        self.debounce_seconds = debounce_seconds
        self.changed_files: set[str] = set()

    def schedule_update(self, path: str | Path) -> None:
        file_path = Path(path)
        if ".git" in file_path.parts:
            return
        self.changed_files.add(file_path.as_posix())

    def drain_changes(self) -> list[str]:
        changes = sorted(self.changed_files)
        self.changed_files.clear()
        return changes
