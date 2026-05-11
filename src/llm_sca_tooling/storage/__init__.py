"""Local persistence layer for LLM-SCA tooling.

Access the store via :class:`WorkspaceStore`::

    store = await WorkspaceStore.initialize(Path("."))
    async with store:
        await store.registry.register_repo(Path("/path/to/repo"))

Do not import raw SQLModel models or SQL from outside this package.
Use the typed store APIs instead.
"""

# Import models first so SQLModel.metadata is populated before create_tables()
import llm_sca_tooling.storage.models  # noqa: F401
from llm_sca_tooling.storage.errors import (
    ArtifactNotFoundError,
    DuplicateRepositoryError,
    GraphIntegrityError,
    GraphQueryLimitError,
    ImportExportError,
    MigrationError,
    RepositoryNotFoundError,
    RunEventSequenceError,
    RunNotFoundError,
    SnapshotNotFoundError,
    StorageError,
    ValidationStorageError,
    WorkspaceIncompatibleError,
    WorkspaceNotFoundError,
)
from llm_sca_tooling.storage.workspace import WorkspaceStatus, WorkspaceStore

__all__ = [
    # Top-level
    "WorkspaceStore",
    "WorkspaceStatus",
    # Errors
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
