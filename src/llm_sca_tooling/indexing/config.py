"""Indexing configuration model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["IndexingConfig"]

_DEFAULT_SKIP_DIRS = frozenset(
    {
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
)


class IndexingConfig(BaseModel):
    """Configuration for a graph build or update run."""

    model_config = ConfigDict(extra="forbid")

    include_globs: list[str] = Field(default_factory=lambda: ["**/*"])
    exclude_globs: list[str] = Field(default_factory=list)
    skip_dirs: frozenset[str] = Field(default_factory=lambda: _DEFAULT_SKIP_DIRS)
    max_file_size_bytes: int = 1_048_576  # 1 MiB
    follow_symlinks: bool = False
    include_hidden: bool = False
    include_generated: bool = False
    language_allowlist: list[str] = Field(default_factory=list)  # empty = all
    backend_timeout_ms: int = 30_000
    graph_slice_limit: int = 2_000
    manifest_chunk_size: int = 1_000

    def is_skip_dir(self, name: str) -> bool:
        return name in self.skip_dirs
