"""File watcher service using ``watchdog``.

``FileWatcherService`` monitors registered repo directories for changes.
On detection it debounces events and triggers ``graph_update`` via the
task manager.  All ``watchdog`` callbacks are dispatched to the running
asyncio event loop via ``loop.call_soon_threadsafe``.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import Any

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["FileWatcherService", "RepoChangeHandler"]

logger = get_logger(__name__)

_DEBOUNCE_SECONDS = 2.0


class RepoChangeHandler:
    """Minimal file-system event handler compatible with watchdog's interface.

    Calls *on_change* with the changed path when a non-``.git`` file is
    modified.  The watchdog ``FileSystemEventHandler`` base is not imported
    directly so that the class remains importable without watchdog installed.
    """

    def __init__(self, on_change: Callable[[str], None]) -> None:
        self._on_change = on_change

    # watchdog calls this method; signature must match watchdog's protocol
    def on_modified(self, event: Any) -> None:  # noqa: ANN401
        if getattr(event, "is_directory", False):
            return
        src: str = getattr(event, "src_path", "")
        if ".git" + "/" in src or src.endswith("/.git") or "/.git/" in src:
            return
        self._on_change(src)

    def on_created(self, event: Any) -> None:  # noqa: ANN401
        self.on_modified(event)

    def on_deleted(self, event: Any) -> None:  # noqa: ANN401
        if getattr(event, "is_directory", False):
            return
        src: str = getattr(event, "src_path", "")
        self._on_change(src)


class FileWatcherService:
    """Watches one or more repository directories and triggers graph updates.

    Args:
        graph_update_fn: Async callable invoked with ``(repo_path, changed_paths)``
            after the debounce window elapses.
        debounce_seconds: Seconds to wait after the last event before triggering.
    """

    def __init__(
        self,
        graph_update_fn: Callable[[str, list[str]], Any] | None = None,
        debounce_seconds: float = _DEBOUNCE_SECONDS,
    ) -> None:
        self._graph_update_fn = graph_update_fn
        self._debounce_seconds = debounce_seconds
        self._watched: dict[str, Any] = {}  # repo_path -> watchdog Watch
        self._pending: dict[str, list[str]] = {}  # repo_path -> [changed paths]
        self._timers: dict[str, threading.Timer] = {}
        self._observer: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Start the watchdog observer thread."""
        try:
            from watchdog.observers import Observer  # noqa: PLC0415
        except ImportError:
            logger.warning("watchdog not installed; FileWatcherService is disabled")
            return
        self._loop = loop or asyncio.get_event_loop()
        self._observer = Observer()
        self._observer.start()
        logger.info("FileWatcherService started")

    def stop(self) -> None:
        """Stop the watchdog observer thread."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        for t in self._timers.values():
            t.cancel()
        self._timers.clear()
        logger.info("FileWatcherService stopped")

    # ------------------------------------------------------------------
    # Watch registration
    # ------------------------------------------------------------------

    def watch(self, repo_path: str) -> None:
        """Register *repo_path* for monitoring."""
        if self._observer is None:
            logger.warning("Observer not started; call start() first")
            return
        if repo_path in self._watched:
            return
        handler = RepoChangeHandler(on_change=lambda p: self._on_change(repo_path, p))
        try:
            from watchdog.observers import Observer  # noqa: PLC0415,F401

            watch = self._observer.schedule(handler, repo_path, recursive=True)
            self._watched[repo_path] = watch
            logger.info("Watching repo: %s", repo_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to watch %s: %s", repo_path, exc)

    def unwatch(self, repo_path: str) -> None:
        """Remove the watch for *repo_path*."""
        if self._observer is None or repo_path not in self._watched:
            return
        self._observer.unschedule(self._watched.pop(repo_path))
        logger.info("Unwatched repo: %s", repo_path)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_change(self, repo_path: str, changed_path: str) -> None:
        """Collect changed paths; reset debounce timer."""
        self._pending.setdefault(repo_path, []).append(changed_path)
        existing = self._timers.pop(repo_path, None)
        if existing is not None:
            existing.cancel()
        t = threading.Timer(
            self._debounce_seconds,
            self._flush,
            args=(repo_path,),
        )
        t.daemon = True
        t.start()
        self._timers[repo_path] = t

    def _flush(self, repo_path: str) -> None:
        """Fire graph update after debounce."""
        changed = self._pending.pop(repo_path, [])
        self._timers.pop(repo_path, None)
        if not changed or self._graph_update_fn is None:
            return
        logger.info(
            "Triggering graph_update for %s (%d files)", repo_path, len(changed)
        )
        if self._loop is not None and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._call_update(repo_path, changed), self._loop
            )

    async def _call_update(self, repo_path: str, changed: list[str]) -> None:
        if self._graph_update_fn is not None:
            await self._graph_update_fn(repo_path, changed)
