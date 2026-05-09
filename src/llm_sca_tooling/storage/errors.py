"""Typed storage errors."""


class StorageError(Exception):
    """Base class for storage failures."""


class WorkspaceNotFoundError(StorageError):
    """Workspace storage root or database is missing."""


class WorkspaceIncompatibleError(StorageError):
    """Workspace storage version is newer than this package supports."""


class MigrationError(StorageError):
    """Migration setup or checksum validation failed."""


class RepositoryNotFoundError(StorageError):
    """Repository was not found."""


class DuplicateRepositoryError(StorageError):
    """Repository lookup or registration is ambiguous."""


class SnapshotNotFoundError(StorageError):
    """Snapshot was not found."""


class GraphIntegrityError(StorageError):
    """Graph endpoint, duplicate, or payload integrity failed."""


class GraphQueryLimitError(StorageError):
    """Graph query exceeded a configured hard limit."""


class RunNotFoundError(StorageError):
    """Run record was not found."""


class RunEventSequenceError(StorageError):
    """Run event append violates append-only sequence rules."""


class ArtifactNotFoundError(StorageError):
    """Artifact record or payload file was not found."""


class ImportExportError(StorageError):
    """Import or export validation failed."""


class ValidationStorageError(StorageError):
    """A schema payload failed validation before storage."""
