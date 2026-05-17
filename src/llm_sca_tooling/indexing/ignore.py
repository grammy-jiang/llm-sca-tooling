"""File and directory ignore policy for the indexing scanner."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.config import IndexingConfig

__all__ = ["IgnorePolicy"]

_BINARY_EXTENSIONS = frozenset(
    {
        ".pyc",
        ".pyo",
        ".so",
        ".dylib",
        ".dll",
        ".exe",
        ".bin",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".ico",
        ".webp",
        ".mp3",
        ".mp4",
        ".wav",
        ".avi",
        ".mov",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".pdf",
        ".docx",
        ".xlsx",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".class",
        ".jar",
    }
)

_LOCK_FILE_NAMES = frozenset(
    {"uv.lock", "poetry.lock", "Pipfile.lock", "package-lock.json", "yarn.lock"}
)


class IgnorePolicy:
    def __init__(self, config: IndexingConfig) -> None:
        self._config = config

    def should_skip_dir(self, name: str) -> bool:
        # Blocklist wins: secret-bearing dirs are excluded unconditionally
        # to honour HC6 even when callers flip ``include_hidden`` on.
        if self._config.is_governance_blocked_dir(name):
            return True
        # Governance allowlist next: ``.agent``, ``.agents``, ``.codex``,
        # and ``.github`` are visible to the indexer so audit evidence can
        # cite them, without enabling every other dot-dir.
        if self._config.is_governance_allowed_dir(name):
            return False
        if name.startswith(".") and not self._config.include_hidden:
            return True
        return self._config.is_skip_dir(name)

    def should_skip_file(self, path: Path, size_bytes: int) -> tuple[bool, str | None]:
        """Return (should_skip, reason) for a file."""
        if size_bytes > self._config.max_file_size_bytes:
            return True, f"file too large ({size_bytes} bytes)"

        suffix = path.suffix.lower()
        if suffix in _BINARY_EXTENSIONS:
            return True, f"binary extension ({suffix})"

        # HC6: secret-bearing file patterns are always skipped, regardless
        # of any ``include_hidden`` or governance allowlist setting.
        if suffix in {".key", ".pem"}:
            return True, f"secret file extension ({suffix})"
        if path.name == ".env" or path.name.startswith(".env."):
            return True, "secret env file"

        if path.name.startswith(".") and not self._config.include_hidden:
            return True, "hidden file"

        return False, None

    def is_lock_file(self, path: Path) -> bool:
        return path.name in _LOCK_FILE_NAMES

    def detect_language(self, path: Path) -> str | None:
        """Return a language label from file extension, or None for unknown."""
        ext = path.suffix.lower()
        return {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".c": "c",
            ".cpp": "c++",
            ".h": "c",
            ".hpp": "c++",
            ".rb": "ruby",
            ".md": "markdown",
            ".rst": "rst",
            ".toml": "toml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
        }.get(ext)

    def is_test_file(self, rel_path: str) -> bool:
        name = Path(rel_path).name
        parts = Path(rel_path).parts
        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or name == "conftest.py"
            or "tests" in parts
            or "test" in parts
        )

    def is_generated_file(self, path: Path) -> bool:
        """Simple heuristic for generated files."""
        name = path.name
        return (
            name.endswith(".g.py")
            or name.endswith("_pb2.py")
            or "generated" in name.lower()
        )
