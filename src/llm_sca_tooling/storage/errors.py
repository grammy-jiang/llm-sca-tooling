"""Typed storage error hierarchy."""

from __future__ import annotations

from llm_sca_tooling.errors import LLMSCAError

__all__ = [
    "StorageError",
    "WorkspaceNotFoundError",
    "WorkspaceIncompatibleError",
    "MigrationError",
    "RepositoryNotFoundError",
    "DuplicateRepositoryError",
    "SnapshotNotFoundError",
    "GraphIntegrityError",
    "GraphQueryLimitError",
    "RunNotFoundError",
    "RunEventSequenceError",
    "ArtifactNotFoundError",
    "ImportExportError",
    "ValidationStorageError",
]


class StorageError(LLMSCAError):
    """Base exception for all storage errors."""


class WorkspaceNotFoundError(StorageError):
    """The workspace directory or database does not exist."""


class WorkspaceIncompatibleError(StorageError):
    """The workspace storage version is incompatible with this build."""


class MigrationError(StorageError):
    """A database migration failed."""


class RepositoryNotFoundError(StorageError):
    """The requested repository is not registered."""


class DuplicateRepositoryError(StorageError):
    """A repository with the same root path is already registered."""


class SnapshotNotFoundError(StorageError):
    """The requested snapshot does not exist."""


class GraphIntegrityError(StorageError):
    """A graph write would violate referential integrity or schema rules."""


class GraphQueryLimitError(StorageError):
    """A graph query exceeded its configured result limit."""


class RunNotFoundError(StorageError):
    """The requested run record does not exist."""


class RunEventSequenceError(StorageError):
    """A run event has a duplicate or non-monotonic sequence number."""


class ArtifactNotFoundError(StorageError):
    """The requested artifact record does not exist."""


class ImportExportError(StorageError):
    """An export/import operation failed."""


class ValidationStorageError(StorageError):
    """A payload failed schema validation before a storage write."""
