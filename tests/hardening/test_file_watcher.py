"""Tests for FileWatcherService."""

from __future__ import annotations

from llm_sca_tooling.hardening.file_watcher import FileWatcherService, RepoChangeHandler


def test_repo_change_handler_skips_git_dirs() -> None:
    received: list[str] = []

    class _Event:
        def __init__(self, path: str, is_directory: bool = False) -> None:
            self.src_path = path
            self.is_directory = is_directory

    handler = RepoChangeHandler(on_change=received.append)
    handler.on_modified(_Event("/.git/COMMIT_EDITMSG"))
    assert not received


def test_repo_change_handler_fires_for_regular_files() -> None:
    received: list[str] = []

    class _Event:
        def __init__(self, path: str) -> None:
            self.src_path = path
            self.is_directory = False

    handler = RepoChangeHandler(on_change=received.append)
    handler.on_modified(_Event("/repo/src/foo.py"))
    assert "/repo/src/foo.py" in received


def test_file_watcher_service_created_without_watchdog(monkeypatch) -> None:
    """Service should initialise even if watchdog is missing."""
    service = FileWatcherService()
    assert service._observer is None


def test_file_watcher_service_stop_without_start() -> None:
    service = FileWatcherService()
    service.stop()  # should not raise
