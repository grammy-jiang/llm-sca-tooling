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

# Hidden dirs that hold governance contracts and overlays.  These are
# indexed by default so implementation-check evidence can cite them
# (closes May-2026 audit Finding 3).
_DEFAULT_GOVERNANCE_ALLOWLIST = frozenset({".agent", ".agents", ".codex", ".github"})

# Names always skipped — even when ``include_hidden`` is True — because
# they hold secrets or credentials.  HC6 forbids red-class data entry.
_DEFAULT_GOVERNANCE_BLOCKLIST = frozenset({"credentials", "secrets"})


class IndexingConfig(BaseModel):
    """Configuration for a graph build or update run."""

    model_config = ConfigDict(extra="forbid")

    include_globs: list[str] = Field(default_factory=lambda: ["**/*"])
    exclude_globs: list[str] = Field(default_factory=list)
    skip_dirs: frozenset[str] = Field(default_factory=lambda: _DEFAULT_SKIP_DIRS)
    governance_allowlist: frozenset[str] = Field(
        default_factory=lambda: _DEFAULT_GOVERNANCE_ALLOWLIST
    )
    governance_blocklist: frozenset[str] = Field(
        default_factory=lambda: _DEFAULT_GOVERNANCE_BLOCKLIST
    )
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

    def is_governance_allowed_dir(self, name: str) -> bool:
        return name in self.governance_allowlist

    def is_governance_blocked_dir(self, name: str) -> bool:
        return name in self.governance_blocklist
