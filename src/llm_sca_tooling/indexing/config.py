"""Indexing configuration."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import StrictBaseModel


class IndexingConfig(StrictBaseModel):
    include_globs: list[str] = Field(default_factory=lambda: ["**/*"])
    exclude_globs: list[str] = Field(default_factory=list)
    max_file_size_bytes: int = 1024 * 1024
    follow_symlinks: bool = False
    include_hidden: bool = True
    include_generated: bool = True
    language_allowlist: list[str] | None = None
    backend_timeout_ms: int = 30_000
    graph_slice_limit: int = 2_000
    manifest_chunk_size: int = 1_000
    workspace_dir_name: str = ".llm-sca"
    run_optional_backends: bool = True
