"""Indexing diagnostics and exceptions."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel
from llm_sca_tooling.schemas.enums import Severity


class IndexDiagnostic(StrictBaseModel):
    diagnostic_id: str
    severity: Severity
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    file_path: str | None = None
    details: JsonObject = Field(default_factory=dict)


class IndexingError(Exception):
    """Base indexing failure."""


class RepositoryResolutionError(IndexingError):
    """Repository could not be resolved or registered."""


class SnapshotCaptureError(IndexingError):
    """Snapshot capture failed."""


class FileScanError(IndexingError):
    """File scan failed."""


class BackendUnavailableError(IndexingError):
    """Optional backend is unavailable."""


class BackendExecutionError(IndexingError):
    """Backend execution failed."""


class BackendParseError(IndexingError):
    """Backend parse failed."""


class GraphMergeError(IndexingError):
    """Graph merge failed."""


class GraphWriteError(IndexingError):
    """Graph write failed."""


class BlameCollectionError(IndexingError):
    """Blame collection failed."""


class SummaryCacheError(IndexingError):
    """Summary cache operation failed."""


class ManifestGenerationError(IndexingError):
    """Graph manifest generation failed."""
