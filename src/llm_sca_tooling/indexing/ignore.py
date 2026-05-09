"""File ignore and skip policy."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from llm_sca_tooling.indexing.config import IndexingConfig

DEFAULT_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".llm-sca",
    ".evidence-sca",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".tox",
    ".nox",
    ".eggs",
}


def is_binary_file(path: Path, sample_size: int = 4096) -> bool:
    try:
        sample = path.read_bytes()[:sample_size]
    except OSError:
        return True
    return b"\0" in sample


def is_generated_path(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith(
        (".generated.py", "_pb2.py", "_pb2_grpc.py")
    ) or "generated" in lowered.split("/")


class IgnorePolicy:
    def __init__(self, config: IndexingConfig) -> None:
        self.config = config

    def skip_dir(self, path: Path, repo_root: Path) -> bool:
        rel = path.relative_to(repo_root).as_posix() if path != repo_root else ""
        if path.name in DEFAULT_SKIP_DIRS:
            return True
        if not self.config.include_hidden and path.name.startswith("."):
            return True
        return any(
            fnmatch.fnmatch(rel, pattern) for pattern in self.config.exclude_globs
        )

    def skip_file_reason(self, path: Path, repo_root: Path) -> str | None:
        rel = path.relative_to(repo_root).as_posix()
        if any(fnmatch.fnmatch(rel, pattern) for pattern in self.config.exclude_globs):
            return "excluded_by_glob"
        if path.is_symlink() and not self.config.follow_symlinks:
            return "symlink"
        if not self.config.include_hidden and path.name.startswith("."):
            return "hidden"
        try:
            size = path.stat().st_size
        except OSError:
            return "stat_failed"
        if size > self.config.max_file_size_bytes:
            return "oversized"
        if is_binary_file(path):
            return "binary"
        if is_generated_path(rel) and not self.config.include_generated:
            return "generated"
        language = detect_language(path)
        if (
            self.config.language_allowlist
            and language not in self.config.language_allowlist
        ):
            return "language_not_allowed"
        return None


def detect_language(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in {".ts", ".tsx"}:
        return "typescript"
    if suffix in {".js", ".jsx", ".mjs", ".cjs"}:
        return "javascript"
    if suffix in {".c", ".h"}:
        return "c"
    if suffix in {".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}:
        return "cpp"
    if suffix in {".md", ".rst"}:
        return "markdown"
    if suffix in {".yml", ".yaml"}:
        return "yaml"
    if suffix == ".toml":
        return "toml"
    if suffix == ".json":
        return "json"
    return "text"
