"""Indexing provenance helpers — re-exports make_provenance from schemas."""

from __future__ import annotations

from llm_sca_tooling.schemas.provenance import (  # noqa: F401
    Provenance,
    RepoRef,
    SnapshotRef,
    SourceSpan,
    make_provenance,
)
